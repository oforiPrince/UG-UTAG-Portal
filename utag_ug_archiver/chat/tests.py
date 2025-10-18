from django.contrib.auth import get_user_model
from django.test import TestCase

from .models import ChatThread, Message
from io import BytesIO
from django.core.files.uploadedfile import SimpleUploadedFile
from chat.models import MessageAttachment


class ChatThreadModelTests(TestCase):
    def setUp(self):
        user_model = get_user_model()
        self.alice = user_model.objects.create_user(
            email='alice@example.com',
            password='testpass123',
            title='Dr.',
            other_name='Alice',
            surname='Anderson',
            gender='Female',
        )
        self.bob = user_model.objects.create_user(
            email='bob@example.com',
            password='testpass123',
            title='Mr.',
            other_name='Bob',
            surname='Baker',
            gender='Male',
        )

    def test_thread_is_unique_for_participants(self):
        first_thread, created_first = ChatThread.objects.get_or_create_thread(self.alice, self.bob)
        second_thread, created_second = ChatThread.objects.get_or_create_thread(self.bob, self.alice)

        self.assertTrue(created_first)
        self.assertFalse(created_second)
        self.assertEqual(first_thread.pk, second_thread.pk)
        self.assertEqual(ChatThread.objects.count(), 1)

    def test_message_updates_last_message_timestamp_and_read_state(self):
        thread, _ = ChatThread.objects.get_or_create_thread(self.alice, self.bob)
        message = Message.objects.create(thread=thread, sender=self.alice, body='Hello Bob')

        thread.refresh_from_db()
        self.assertEqual(thread.last_message_at, message.created_at)

        thread.mark_messages_as_read(self.bob)
        message.refresh_from_db()
        self.assertIsNotNone(message.read_at)

        # Alice reading her own message should not change read_at timestamp
        original_read_at = message.read_at
        thread.mark_messages_as_read(self.alice)
        message.refresh_from_db()
        self.assertEqual(message.read_at, original_read_at)

    def test_attachment_upload_and_download_permissions(self):
        thread, _ = ChatThread.objects.get_or_create_thread(self.alice, self.bob)
        # create a small fake image
        img_bytes = b"\x89PNG\r\n\x1a\n" + b"\x00" * 100
        uploaded = SimpleUploadedFile('test.png', img_bytes, content_type='image/png')

        # create message and attach
        message = Message(thread=thread, sender=self.alice)
        message.set_plaintext('See attachment')
        message.save()

        att = MessageAttachment(message=message, filename='test.png', content_type='image/png')
        att.set_content(img_bytes)
        att.save()

        # bob can download
        c = self.client
        c.login(email='bob@example.com', password='testpass123')
        resp = c.get(att.download_url())
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.content, img_bytes)

        # unauthorized user cannot download
        other = get_user_model().objects.create_user(
            email='eve@example.com',
            password='testpass123',
            other_name='Eve',
            surname='Eaves',
            title='Ms.',
            gender='Female'
        )
        c.logout()
        c.login(email='eve@example.com', password='testpass123')
        resp2 = c.get(att.download_url())
        self.assertEqual(resp2.status_code, 404)
