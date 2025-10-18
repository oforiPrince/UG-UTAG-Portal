from django.conf import settings
from django.db import models
from django.db.models import Q
from django.utils import timezone
from django.core.files.base import ContentFile
from django.urls import reverse
from django.core.files.storage import default_storage
from django.conf import settings
import os

from cryptography.fernet import Fernet


def generate_encryption_key():
	return Fernet.generate_key()


def ensure_bytes(value):
	if value is None:
		return None
	if isinstance(value, (bytes, bytearray)):
		return bytes(value)
	if isinstance(value, memoryview):
		return value.tobytes()
	return str(value).encode('utf-8')


class ChatThreadQuerySet(models.QuerySet):
	def for_user(self, user):
		return (
			self.filter(Q(user_one=user) | Q(user_two=user))
			.select_related('user_one', 'user_two')
			.order_by('-last_message_at', '-updated_at')
		)


class ChatThreadManager(models.Manager):
	def get_queryset(self):
		return ChatThreadQuerySet(self.model, using=self._db)

	def for_user(self, user):
		return self.get_queryset().for_user(user)

	def _normalize_users(self, user_a, user_b):
		if user_a.pk == user_b.pk:
			raise ValueError('Cannot create a chat thread with the same user on both sides.')
		return (user_a, user_b) if user_a.pk < user_b.pk else (user_b, user_a)

	def get_or_create_thread(self, user_a, user_b):
		user_one, user_two = self._normalize_users(user_a, user_b)
		thread, created = self.get_or_create(user_one=user_one, user_two=user_two)
		if created:
			thread.encryption_key = generate_encryption_key()
			thread.save(update_fields=['encryption_key'])
		return thread, created


class ChatThread(models.Model):
	user_one = models.ForeignKey(
		settings.AUTH_USER_MODEL,
		on_delete=models.CASCADE,
		related_name='threads_as_user_one',
	)
	user_two = models.ForeignKey(
		settings.AUTH_USER_MODEL,
		on_delete=models.CASCADE,
		related_name='threads_as_user_two',
	)
	created_at = models.DateTimeField(auto_now_add=True)
	updated_at = models.DateTimeField(auto_now=True)
	last_message_at = models.DateTimeField(default=timezone.now)
	encryption_key = models.BinaryField(editable=False, null=True, blank=True)

	objects = ChatThreadManager()

	class Meta:
		ordering = ('-last_message_at', '-updated_at')
		constraints = [
			models.UniqueConstraint(
				fields=('user_one', 'user_two'),
				name='unique_chat_thread_participants',
			),
		]

	def save(self, *args, **kwargs):
		if self.user_one_id is not None and self.user_two_id is not None:
			if self.user_one_id == self.user_two_id:
				raise ValueError('ChatThread participants must be different users.')
			if self.user_one_id > self.user_two_id:
				self.user_one_id, self.user_two_id = self.user_two_id, self.user_one_id
		if self.encryption_key in (None, b''):
			self.encryption_key = generate_encryption_key()
		super().save(*args, **kwargs)

	def __str__(self):
		return f'Thread between {self.user_one.get_full_name()} and {self.user_two.get_full_name()}'

	def participants(self):
		return (self.user_one, self.user_two)

	def other_participant(self, user):
		if user.pk == self.user_one_id:
			return self.user_two
		if user.pk == self.user_two_id:
			return self.user_one
		raise ValueError('User is not part of this chat thread.')

	def is_participant(self, user):
		return user.pk in {self.user_one_id, self.user_two_id}

	def _fernet(self):
		return Fernet(ensure_bytes(self.encryption_key))

	def encrypt_text(self, text):
		if text is None:
			text = ''
		if isinstance(text, str):
			text = text.encode('utf-8')
		return self._fernet().encrypt(text)

	def decrypt_text(self, ciphertext):
		if not ciphertext:
			return ''
		return self._fernet().decrypt(ensure_bytes(ciphertext)).decode('utf-8')

	def mark_messages_as_read(self, reader):
		Message.objects.filter(thread=self, read_at__isnull=True).exclude(sender=reader).update(
			read_at=timezone.now()
		)


class Message(models.Model):
	thread = models.ForeignKey(ChatThread, on_delete=models.CASCADE, related_name='messages')
	sender = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='messages_sent')
	ciphertext = models.BinaryField(editable=False, null=True, blank=True)
	created_at = models.DateTimeField(auto_now_add=True)
	read_at = models.DateTimeField(null=True, blank=True)

	_plaintext_cache = None

	class Meta:
		ordering = ('created_at',)

	

	def save(self, *args, **kwargs):
		is_new = self.pk is None
		if self.ciphertext in (None, b'') and self._plaintext_cache is not None:
			self.ciphertext = self.thread.encrypt_text(self._plaintext_cache)
		super().save(*args, **kwargs)
		if is_new:
			ChatThread.objects.filter(pk=self.thread_id).update(
				last_message_at=self.created_at,
				updated_at=timezone.now(),
			)

	def __init__(self, *args, **kwargs):
		# Accept legacy 'body' kw for convenience in tests and callers
		body = kwargs.pop('body', None)
		super().__init__(*args, **kwargs)
		if body is not None:
			# If thread is already attached, set plaintext now; otherwise caller may set later
			try:
				if getattr(self, 'thread', None):
					self.set_plaintext(body)
				else:
					# store in cache for save path
					self._plaintext_cache = body
			except Exception:
				# be permissive during initialization
				self._plaintext_cache = body

	def set_plaintext(self, value):
		self._plaintext_cache = value or ''
		if value is not None:
			self.ciphertext = self.thread.encrypt_text(value)

	@property
	def plaintext(self):
		if self._plaintext_cache is not None:
			return self._plaintext_cache
		if not self.ciphertext:
			return ''
		self._plaintext_cache = self.thread.decrypt_text(self.ciphertext)
		return self._plaintext_cache

	def mark_as_read(self):
		if self.read_at is None:
			self.read_at = timezone.now()
			self.save(update_fields=['read_at'])


class ChatGroup(models.Model):
	name = models.CharField(max_length=120)
	created_by = models.ForeignKey(
		settings.AUTH_USER_MODEL,
		on_delete=models.CASCADE,
		related_name='chat_groups_created',
	)
	encryption_key = models.BinaryField(editable=False, null=True, blank=True)
	created_at = models.DateTimeField(auto_now_add=True)
	updated_at = models.DateTimeField(auto_now=True)
	members = models.ManyToManyField(
		settings.AUTH_USER_MODEL,
		through='GroupMembership',
		through_fields=('group', 'user'),
		related_name='chat_groups',
	)

	class Meta:
		ordering = ('name',)
		unique_together = ('name', 'created_by')

	def __str__(self):
		return self.name

	def save(self, *args, **kwargs):
		if self.encryption_key in (None, b''):
			self.encryption_key = generate_encryption_key()
		super().save(*args, **kwargs)

	def _fernet(self):
		return Fernet(ensure_bytes(self.encryption_key))

	def encrypt_text(self, text):
		if text is None:
			text = ''
		if isinstance(text, str):
			text = text.encode('utf-8')
		return self._fernet().encrypt(text)

	def decrypt_text(self, ciphertext):
		if not ciphertext:
			return ''
		return self._fernet().decrypt(ensure_bytes(ciphertext)).decode('utf-8')

	def is_member(self, user):
		return self.members.filter(pk=user.pk).exists()

	def can_manage_members(self, user):
		return user == self.created_by or user.is_superuser


class GroupMembership(models.Model):
	group = models.ForeignKey(ChatGroup, on_delete=models.CASCADE, related_name='membership_records')
	user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='group_memberships')
	added_by = models.ForeignKey(
		settings.AUTH_USER_MODEL,
		on_delete=models.SET_NULL,
		null=True,
		blank=True,
		related_name='group_memberships_added',
	)
	added_at = models.DateTimeField(auto_now_add=True)

	class Meta:
		unique_together = ('group', 'user')

	def __str__(self):
		return f'{self.user.get_full_name()} in {self.group.name}'


class GroupMessage(models.Model):
	group = models.ForeignKey(ChatGroup, on_delete=models.CASCADE, related_name='messages')
	sender = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='group_messages_sent')
	ciphertext = models.BinaryField(editable=False, null=True, blank=True)
	created_at = models.DateTimeField(auto_now_add=True)
	read_by = models.ManyToManyField(
		settings.AUTH_USER_MODEL,
		through='GroupMessageRead',
		related_name='group_messages_read',
		blank=True,
	)

	_plaintext_cache = None

	class Meta:
		ordering = ('created_at',)

	def __str__(self):
		return f'Group message in {self.group.name} ({self.created_at:%Y-%m-%d %H:%M})'

	def save(self, *args, **kwargs):
		if self.ciphertext in (None, b'') and self._plaintext_cache is not None:
			self.ciphertext = self.group.encrypt_text(self._plaintext_cache)
		super().save(*args, **kwargs)

	def __init__(self, *args, **kwargs):
		# Accept legacy 'body' kw for convenience
		body = kwargs.pop('body', None)
		super().__init__(*args, **kwargs)
		if body is not None:
			try:
				if getattr(self, 'group', None):
					self.set_plaintext(body)
				else:
					self._plaintext_cache = body
			except Exception:
				self._plaintext_cache = body

	def set_plaintext(self, value):
		self._plaintext_cache = value or ''
		if value is not None:
			self.ciphertext = self.group.encrypt_text(value)

	@property
	def plaintext(self):
		if self._plaintext_cache is not None:
			return self._plaintext_cache
		if not self.ciphertext:
			return ''
		self._plaintext_cache = self.group.decrypt_text(self.ciphertext)
		return self._plaintext_cache

	def mark_read_for(self, user):
		GroupMessageRead.objects.get_or_create(message=self, user=user)


class GroupMessageRead(models.Model):
	message = models.ForeignKey(GroupMessage, on_delete=models.CASCADE, related_name='read_receipts')
	user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='group_message_receipts')
	read_at = models.DateTimeField(auto_now_add=True)

	class Meta:
		unique_together = ('message', 'user')

	def __str__(self):
		return f'{self.user.get_full_name()} read {self.message_id} at {self.read_at}'


class MessageAttachment(models.Model):
	"""Attachment for direct Message. Content is encrypted using thread key."""
	message = models.ForeignKey(Message, on_delete=models.CASCADE, related_name='attachments')
	filename = models.CharField(max_length=255)
	content_type = models.CharField(max_length=128, blank=True, null=True)
	size = models.PositiveIntegerField(default=0)
	ciphertext = models.BinaryField(editable=False, null=True, blank=True)
	# file_path stores encrypted file in configured storage
	file_path = models.CharField(max_length=500, blank=True, null=True)
	# optional encrypted thumbnail (for PDFs)
	thumbnail_path = models.CharField(max_length=500, blank=True, null=True)

	def set_content(self, data_bytes):
		# encrypt the raw bytes using the parent thread key and save to storage
		if not self.message or not self.message.thread:
			raise ValueError('Message and thread must be set before saving content')
		ciphertext = self.message.thread._fernet().encrypt(data_bytes)
		# build path: attachments/thread_<threadid>/<filename>.enc
		base_dir = os.path.join('attachments', f'thread_{self.message.thread_id}')
		filename = f"{self.filename}.enc"
		path = os.path.join(base_dir, filename)
		# ensure unique path
		counter = 1
		orig_path = path
		while default_storage.exists(path):
			path = os.path.join(base_dir, f"{self.filename}-{counter}.enc")
			counter += 1
		default_storage.save(path, ContentFile(ciphertext))
		self.file_path = path
		self.size = len(data_bytes)

		# If this is a PDF, try to generate a PNG thumbnail (first page) if PyMuPDF is available
		try:
			if self.content_type and self.content_type == 'application/pdf':
				try:
					import fitz  # PyMuPDF

					# create pixmap of first page
					doc = fitz.open(stream=data_bytes, filetype='pdf')
					if doc.page_count > 0:
						page = doc.load_page(0)
						pix = page.get_pixmap(matrix=fitz.Matrix(1, 1), alpha=False)
						png_bytes = pix.tobytes(output='png')
						# encrypt and save thumbnail
						thumb_cipher = self.message.thread._fernet().encrypt(png_bytes)
						thumb_dir = os.path.join('attachments', f'thread_{self.message.thread_id}', 'thumbs')
						thumb_name = f"{self.filename}.thumb.png.enc"
						thumb_path = os.path.join(thumb_dir, thumb_name)
						counter = 1
						while default_storage.exists(thumb_path):
							thumb_path = os.path.join(thumb_dir, f"{self.filename}-{counter}.thumb.png.enc")
							counter += 1
						default_storage.save(thumb_path, ContentFile(thumb_cipher))
						self.thumbnail_path = thumb_path
				except Exception:
					# if fitz not available or generation fails, skip silently
					pass
		except Exception:
			pass

	def get_content(self):
		# read encrypted bytes from storage if available, else fallback to ciphertext
		if self.file_path:
			with default_storage.open(self.file_path, 'rb') as f:
				ciphertext = f.read()
		elif self.ciphertext:
			ciphertext = bytes(self.ciphertext)
		else:
			return b''
		# decrypt using thread fernet and return raw bytes
		return self.message.thread._fernet().decrypt(ciphertext)

	def get_thumbnail_content(self):
		if not self.thumbnail_path:
			return None
		with default_storage.open(self.thumbnail_path, 'rb') as f:
			thumb_cipher = f.read()
		return self.message.thread._fernet().decrypt(thumb_cipher)

	def thumbnail_url(self):
		from django.urls import reverse

		if not self.thumbnail_path:
			return None
		return reverse('chat:download_message_attachment_thumbnail', args=[self.id])

	def download_url(self):
		return reverse('chat:download_message_attachment', args=[self.id])

	@property
	def is_image(self):
		return bool(self.content_type and self.content_type.startswith('image/'))


class GroupMessageAttachment(models.Model):
	"""Attachment for GroupMessage. Content encrypted with group key."""
	message = models.ForeignKey(GroupMessage, on_delete=models.CASCADE, related_name='attachments')
	filename = models.CharField(max_length=255)
	content_type = models.CharField(max_length=128, blank=True, null=True)
	size = models.PositiveIntegerField(default=0)
	ciphertext = models.BinaryField(editable=False, null=True, blank=True)
	file_path = models.CharField(max_length=500, blank=True, null=True)
	thumbnail_path = models.CharField(max_length=500, blank=True, null=True)

	def set_content(self, data_bytes):
		if not self.message or not self.message.group:
			raise ValueError('Message and group must be set before saving content')
		ciphertext = self.message.group._fernet().encrypt(data_bytes)
		base_dir = os.path.join('attachments', f'group_{self.message.group_id}')
		filename = f"{self.filename}.enc"
		path = os.path.join(base_dir, filename)
		counter = 1
		while default_storage.exists(path):
			path = os.path.join(base_dir, f"{self.filename}-{counter}.enc")
			counter += 1
		default_storage.save(path, ContentFile(ciphertext))
		self.file_path = path
		self.size = len(data_bytes)

		try:
			if self.content_type and self.content_type == 'application/pdf':
				try:
					import fitz

					doc = fitz.open(stream=data_bytes, filetype='pdf')
					if doc.page_count > 0:
						page = doc.load_page(0)
						pix = page.get_pixmap(matrix=fitz.Matrix(1, 1), alpha=False)
						png_bytes = pix.tobytes(output='png')
						thumb_cipher = self.message.group._fernet().encrypt(png_bytes)
						thumb_dir = os.path.join('attachments', f'group_{self.message.group_id}', 'thumbs')
						thumb_name = f"{self.filename}.thumb.png.enc"
						thumb_path = os.path.join(thumb_dir, thumb_name)
						counter = 1
						while default_storage.exists(thumb_path):
							thumb_path = os.path.join(thumb_dir, f"{self.filename}-{counter}.thumb.png.enc")
							counter += 1
						default_storage.save(thumb_path, ContentFile(thumb_cipher))
						self.thumbnail_path = thumb_path
				except Exception:
					pass
		except Exception:
			pass

	def get_content(self):
		if self.file_path:
			with default_storage.open(self.file_path, 'rb') as f:
				ciphertext = f.read()
		elif self.ciphertext:
			ciphertext = bytes(self.ciphertext)
		else:
			return b''
		return self.message.group._fernet().decrypt(ciphertext)

	def get_thumbnail_content(self):
		if not self.thumbnail_path:
			return None
		with default_storage.open(self.thumbnail_path, 'rb') as f:
			thumb_cipher = f.read()
		return self.message.group._fernet().decrypt(thumb_cipher)

	def thumbnail_url(self):
		from django.urls import reverse

		if not self.thumbnail_path:
			return None
		return reverse('chat:download_group_message_attachment_thumbnail', args=[self.id])

	def download_url(self):
		return reverse('chat:download_group_message_attachment', args=[self.id])

	@property
	def is_image(self):
		return bool(self.content_type and self.content_type.startswith('image/'))
