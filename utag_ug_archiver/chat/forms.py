from django import forms
from django.contrib.auth import get_user_model
from django.db.models import Q

User = get_user_model()


class ThreadStartForm(forms.Form):
    recipient = forms.ModelChoiceField(queryset=User.objects.none(), label='Recipient')
    initial_message = forms.CharField(
        label='Message',
        widget=forms.Textarea(attrs={'rows': 3, 'placeholder': 'Type your message here...'}),
        max_length=2000,
    )

    def __init__(self, user, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.user = user
        queryset = User.objects.exclude(pk=user.pk).order_by('surname', 'other_name')
        self.fields['recipient'].queryset = queryset
        self.fields['recipient'].widget.attrs.update({'class': 'form-select'})
        self.fields['initial_message'].widget.attrs.update({'class': 'form-control'})

    def clean_recipient(self):
        recipient = self.cleaned_data['recipient']
        if recipient == self.user:
            raise forms.ValidationError('You cannot start a chat with yourself.')
        return recipient


class DirectMessageForm(forms.Form):
    body = forms.CharField(
        widget=forms.Textarea(
            attrs={
                'rows': 3,
                'placeholder': 'Write a message…',
                'class': 'form-control',
            }
        ),
        label='',
        max_length=2000,
    )
    attachment = forms.FileField(required=False)


class GroupCreateForm(forms.Form):
    name = forms.CharField(
        max_length=120,
        widget=forms.TextInput(attrs={
            'class': 'form-control', 
            'placeholder': 'Executive Strategy Team',
            'required': True
        }),
        label='Group name',
    )
    members = forms.ModelMultipleChoiceField(
        queryset=User.objects.none(),
        widget=forms.CheckboxSelectMultiple,
        label='Select members',
        required=False,
        help_text='Select UTAG members to add to this group'
    )

    def __init__(self, creator, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.creator = creator
        # All users except the creator
        queryset = User.objects.exclude(pk=creator.pk).filter(
            is_active=True
        ).order_by('surname', 'other_name')
        self.fields['members'].queryset = queryset


class GroupMessageForm(forms.Form):
    body = forms.CharField(
        widget=forms.Textarea(
            attrs={
                'rows': 3,
                'placeholder': 'Share an update…',
                'class': 'form-control',
            }
        ),
        label='',
        max_length=2000,
    )
    attachment = forms.FileField(required=False)


class GroupMemberAddForm(forms.Form):
    user = forms.ModelChoiceField(queryset=User.objects.none(), label='Executive member')

    def __init__(self, group, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.group = group
        executive_filter = Q(is_active_executive=True) | Q(groups__name='Executive')
        queryset = (
            User.objects.filter(executive_filter)
            .exclude(group_memberships__group=group)
            .order_by('surname', 'other_name')
            .distinct()
        )
        self.fields['user'].queryset = queryset
        self.fields['user'].widget.attrs.update({'class': 'form-select'})

    def clean_user(self):
        user = self.cleaned_data['user']
        if self.group.is_member(user):
            raise forms.ValidationError('This member is already in the group.')
        return user
