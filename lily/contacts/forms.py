from django import forms
from django.core.exceptions import ValidationError
from django.core.urlresolvers import reverse_lazy
from django.core.validators import validate_email
from django.utils.translation import ugettext as _

from lily.accounts.models import Account
from lily.contacts.models import Contact, Function
from lily.socialmedia.connectors import Twitter
from lily.socialmedia.models import SocialMedia
from lily.tags.forms import TagsFormMixin
from lily.utils.forms import HelloLilyModelForm
from lily.utils.forms.fields import TagsField
from lily.utils.forms.widgets import ShowHideWidget, BootstrapRadioFieldRenderer, AddonTextInput, AjaxSelect2Widget
from lily.utils.forms.mixins import FormSetFormMixin
from lily.utils.models import EmailAddress
from lily.socialmedia.connectors import Twitter, LinkedIn


class AddContactQuickbuttonForm(HelloLilyModelForm):
    """
    Form to add an account with the absolute minimum of information.
    """
    account = forms.ModelChoiceField(
        label=_('Works at'),
        required=False,
        queryset=Account.objects,
        empty_label=_('Select an account'),
        widget=AjaxSelect2Widget(
            url=reverse_lazy('json_account_list'),
            model=Account,
        ),
    )
    emails = TagsField(
        label=_('E-mail addresses'),
        required=False,
    )

    phone = forms.CharField(label=_('Phone number'), max_length=40, required=False)

    def __init__(self, *args, **kwargs):
        """
        Overload super().__init__ to change auto_id to prevent clashing form field id's with
        other forms.
        """
        kwargs.update({
            'auto_id': 'id_contact_quickbutton_%s'
        })

        super(AddContactQuickbuttonForm, self).__init__(*args, **kwargs)

        # Provide filtered query set
        self.fields['account'].queryset = Account.objects.all()

    def clean_emails(self):
        """
        Prevent multiple contacts with the same email address when adding
        """
        for email in self.cleaned_data['emails']:
            # Check if input is a real email address
            validate_email(email)
            # Check if email address already exists under different account
            if Contact.objects.filter(email_addresses__email_address__iexact=email).exists():
                raise ValidationError(
                    _('E-mail address already in use.'),
                    code='invalid',
                )
        return self.cleaned_data['emails']

    def clean(self):
        """
        Form validation: all fields should be unique.
        """
        cleaned_data = super(AddContactQuickbuttonForm, self).clean()

        # Check if at least first or last name has been provided.
        if not cleaned_data.get('first_name') and not cleaned_data.get('last_name'):
            self._errors['first_name'] = self._errors['last_name'] = self.error_class([_('Name can\'t be empty')])

        return cleaned_data

    def save(self, commit=True):
        """
        Save Many2Many email addresses to instance.
        """
        instance = super(AddContactQuickbuttonForm, self).save(commit=commit)

        if commit:
            first = True
            for email in self.cleaned_data['emails']:
                email_address = EmailAddress.objects.create(
                    email_address=email,
                    is_primary=first,
                    tenant=instance.tenant
                )
                instance.email_addresses.add(email_address)
                first = False

        return instance

    class Meta:
        model = Contact
        fields = ('first_name', 'preposition', 'last_name', 'account', 'emails', 'phone')


class CreateUpdateContactForm(FormSetFormMixin, TagsFormMixin):
    """
    Form to add a contact which all fields available.
    """
    account = forms.ModelChoiceField(
        label=_('Works at'),
        required=False,
        queryset=Account.objects,
        empty_label=_('Select an account'),
        widget=AjaxSelect2Widget(
            url=reverse_lazy('json_account_list'),
            model=Account,
        ),
    )

    twitter = forms.CharField(label=_('Twitter'), required=False, widget=AddonTextInput(icon_attrs={
        'class': 'icon-twitter',
        'position': 'left',
        'is_button': False
    }))
    linkedin = forms.CharField(label=_('LinkedIn'), required=False, widget=AddonTextInput(icon_attrs={
        'class': 'icon-linkedin',
        'position': 'left',
        'is_button': False
    }))

    def __init__(self, *args, **kwargs):
        super(CreateUpdateContactForm, self).__init__(*args, **kwargs)

        # Try providing initial account info
        is_working_at = Function.objects.filter(contact=self.instance).values_list('account_id', flat=True)
        if len(is_working_at) == 1:
            self.fields['account'].initial = is_working_at[0]

        if self.instance.pk:
            twitter = self.instance.social_media.filter(name='twitter').first()
            self.fields['twitter'].initial = twitter.username if twitter else ''
            linkedin = self.instance.social_media.filter(name='linkedin').first()
            self.fields['linkedin'].initial = linkedin.username if linkedin else ''

        self.fields['addresses'].form_attrs = {
            'exclude_address_types': ['visiting'],
            'extra_form_kwargs': {
                'initial': {
                    'type': 'home',
                }
            }
        }

    def clean_twitter(self):
        """
        Check if added twitter name is a valid twitter name.

        Returns:
            string: twitter username or empty string.
        """
        twitter = self.cleaned_data.get('twitter')

        if twitter:
            try:
                twit = Twitter(twitter)
            except ValueError:
                raise ValidationError(_('Please enter a valid username or link'), code='invalid')
            else:
                return twit.username
        return twitter

    def clean_linkedin(self):
        """
        Check if added linkedin url is a valid linkedin url.

        Returns:
            string: linkedin username or empty string.
        """
        linkedin = self.cleaned_data['linkedin']

        if linkedin:
            try:
                lin = LinkedIn(linkedin)
            except ValueError:
                raise ValidationError(_('Please enter a valid username or link'), code='invalid')
            else:
                return lin.username

        return linkedin

    def clean(self):
        """
        Form validation: fill in at least first or last name.

        Returns:
            dict: cleaned data of all fields.
        """
        cleaned_data = super(CreateUpdateContactForm, self).clean()

        # Check if at least first or last name has been provided.
        if not cleaned_data.get('first_name') and not cleaned_data.get('last_name'):
            self._errors['first_name'] = self._errors['last_name'] = self.error_class([_('Name can\'t be empty')])

        return cleaned_data

    def save(self, commit=True):
        """
        Save contact to instance, and to database if commit is True.

        Returns:
            instance: an instance of the contact model
        """
        instance = super(CreateUpdateContactForm, self).save(commit)

        if commit:
            twitter_input = self.cleaned_data.get('twitter')
            linkedin_input = self.cleaned_data.get('linkedin')

            if twitter_input and instance.social_media.filter(name='twitter').exists():
                # There is input and there are one or more twitters connected, so we get the first of those.
                twitter_queryset = self.instance.social_media.filter(name='twitter')
                if self.fields['twitter'].initial:  # Only filter on initial if there is initial data.
                    twitter_queryset = twitter_queryset.filter(username=self.fields['twitter'].initial)
                twitter_instance = twitter_queryset.first()

                # And we edit it to store our new input.
                twitter = Twitter(self.cleaned_data.get('twitter'))
                twitter_instance.username = twitter.username
                twitter_instance.profile_url = twitter.profile_url
                twitter_instance.save()
            elif twitter_input:
                # There is input but no connected twitter, so we create a new one.
                twitter = Twitter(self.cleaned_data.get('twitter'))
                twitter_instance = SocialMedia.objects.create(
                    name='twitter',
                    username=twitter.username,
                    profile_url=twitter.profile_url,
                )
                instance.social_media.add(twitter_instance)
            else:
                # There is no input and zero or more connected twitters, so we delete them all.
                instance.social_media.filter(name='twitter').delete()

            if linkedin_input and instance.social_media.filter(name='linkedin').exists():
                # There is input and there are one or more linkedins connected, so we get the first of those.
                linkedin_instance = self.instance.social_media.filter(name='linkedin')
                if self.fields['linkedin'].initial:  # Only filter on initial if there is initial data.
                    linkedin_instance = linkedin_instance.filter(username=self.fields['linkedin'].initial)
                linkedin_instance = linkedin_instance.first()

                # And we edit it to store our new input.
                linkedin = LinkedIn(self.cleaned_data.get('linkedin'))
                linkedin_instance.username = linkedin.username
                linkedin_instance.profile_url = linkedin.profile_url
                linkedin_instance.save()
            elif linkedin_input:
                # There is input but no connected linkedin, so we create a new one.
                linkedin = LinkedIn(self.cleaned_data.get('linkedin'))
                linkedin_instance = SocialMedia.objects.create(
                    name='linkedin',
                    username=linkedin.username,
                    profile_url=linkedin.profile_url,
                )
                instance.social_media.add(linkedin_instance)
            else:
                # There is no input and zero or more connected twitters, so we delete them all.
                instance.social_media.filter(name='linkedin').delete()

        return instance

    class Meta:
        model = Contact
        fields = ('salutation', 'gender', 'first_name', 'preposition', 'last_name', 'account', 'description',
                  'email_addresses', 'phone_numbers', 'addresses', )
        widgets = {
            'description': ShowHideWidget(forms.Textarea(attrs={
                'rows': 3,
            })),
            'salutation': forms.widgets.RadioSelect(renderer=BootstrapRadioFieldRenderer, attrs={
                'data-skip-uniform': 'true',
                'data-uniformed': 'true',
            }),
            'gender': forms.widgets.RadioSelect(renderer=BootstrapRadioFieldRenderer, attrs={
                'data-skip-uniform': 'true',
                'data-uniformed': 'true',
            }),
        }
