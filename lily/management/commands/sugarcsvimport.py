import csv
import gc
import logging
import os

from django.core.files.storage import default_storage
from django.core.management.base import BaseCommand
from django.db import DataError

from lily.accounts.models import Account, Website
from lily.contacts.models import Contact
from lily.socialmedia.models import SocialMedia
from lily.users.models import LilyUser
from lily.utils.functions import parse_address, _isint
from lily.utils.models.models import Address, PhoneNumber, EmailAddress, COUNTRIES


logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = """Import accounts and then contacts from separate csv files.

E.g.:
* sugarcsvimport accounts /local/sandbox/hellolily-import/partners.csv  10
* sugarcsvimport contacts /local/sandbox/hellolily-import/contacten.csv  10
"""
    # Some countries are not in 2-code or misspelled
    country_map = {
        'NEDERLAND': 'NL',
        'NETHERLANDS': 'NL',
        'THE NETHERLANDS': 'NL',
        'HOLLAND': 'NL',
        'NDERLAND': 'NL',
        'NEDELAND': 'NL',
        'NLN': 'NL',
        'THE NETHERLAND': 'NL',
        'SURINAME': 'SR',
        'BELGIE': 'BE',
        'BELGIUM': 'BE',
        'BELGI&#235;': 'BE',
        'DUITSLAND': 'DE',
        'GERMANY': 'DE',
        'LUXEMBOURG': 'LU',
        'MAROC': 'MA',
        'UK': 'GB',
        'UNITED KINGDOM': 'GB',
        'FINLAND': 'FI',
        'NEDERLANDSE ANTILLEN': 'AN',
        'CANADA': 'CA',
        'SPAIN': 'ES',
        'SPANJE': 'ES',
        'ESPANA': 'ES',
        'USA': 'US',
        'U.S.A.': 'US',
        'AUSTRALIA': 'AU',
        'IRELAND': 'IR',
        'FRANKRIJK': 'FR',
        'FRANCE': 'FR',
        'POLEN': 'PL',
        'MALTA': 'MT',
        'PHILIPPINES': 'PH',
    }

    country_codes = set([country[0] for country in COUNTRIES])
    user_mapping = {}
    already_logged = set()

    def handle(self, model, csvfile, tenant_pk, sugar='1', **kwargs):
        self.tenant_pk = tenant_pk
        self.sugar_import = sugar == '1'

        # Get user mapping from env vars
        user_string = os.environ.get('USERMAPPING')
        for user in user_string.split(';'):
            sugar, lily = user.split(':')
            self.user_mapping[sugar] = lily

        if model in ['account', 'accounts']:
            logger.info('importing accounts started')

            for row in self.read_csvfile(csvfile):
                self._create_account_data(row)
                gc.collect()
            logger.info('importing accounts finished')

        elif model in ['contact', 'contacts']:
            logger.info('importing contacts started')

            for row in self.read_csvfile(csvfile):
                self._create_contact_data(row)
                gc.collect()
            logger.info('importing contacts finished')

        else:
            raise Exception('unknown model: %s' % model)

    def read_csvfile(self, file_name):
        """
        Read from path assuming it's a file with ',' separated values.
        """
        # Newlines are breaking correct csv parsing. Write correct temporary file to parse.
        csv_file = default_storage.open(file_name, 'rU')
        reader = csv.DictReader(csv_file, delimiter=',', quoting=csv.QUOTE_ALL)
        for row in reader:
            yield row

    def _create_account_data(self, values):
        """
        Create Account from given dict.

        Arguments:
            values (dict): information with account information
        """
        column_attribute_mapping = {
            'VoIPGRID ID': 'customer_id',
            'Name': 'name',
            '': 'flatname',
            '': 'status',
            '': 'company_size',
            '': 'logo',
            'Description': 'description',
            '': 'legalentity',
            '': 'taxnumber',
            '': 'bankaccountnumber',
            'KvK': 'cocnumber',
            '': 'iban',
            '': 'bic',
            'ID': 'import_id',
        }

        # Create account
        account_kwargs = dict()
        for column, value in values.items():
            if value and column in column_attribute_mapping:
                attribute = column_attribute_mapping.get(column)
                account_kwargs[attribute] = value

        if not len(account_kwargs):
            return
        if 'name' not in account_kwargs or not account_kwargs['name']:
            return
        try:
            account = Account.objects.get(
                tenant_id=self.tenant_pk,
                import_id=account_kwargs['import_id']
            )
        except Account.DoesNotExist:
            account = Account.objects.filter(tenant_id=self.tenant_pk, name=account_kwargs['name']).first()
            if not account:
                account = Account(tenant_id=self.tenant_pk)

        for k, v in account_kwargs.items():
            setattr(account, k, v)

        # Satisfy m2m contraints.
        try:
            account.save()
        except DataError:
            logger.error(u'DataError for %s' % account_kwargs)
            return

        # Create addresses
        self._create_address(
            account,
            'visiting',
            values.get('Billing Street'),
            values.get('Billing Postal Code'),
            values.get('Billing City'),
            values.get('Billing Country')
        )
        self._create_address(
            account,
            'shipping',
            values.get('Shipping Street'),
            values.get('Shipping Postal Code'),
            values.get('Shipping City'),
            values.get('Shipping Country')
        )

        # Create email addresses
        self._create_email_addresses(account, values)

        # Create phone numbers
        self._create_phone(account, 'work', values.get('Office Phone'))
        self._create_phone(account, 'work', values.get('Alternate Phone'))
        self._create_phone(account, 'other', values.get('Fax'), other_type='fax')

        # Create website
        self._create_website(account, values.get('Website'))

        # Create social media
        self._create_social_media(account, 'linkedin', values.get('LinkedIn'))
        self._create_social_media(account, 'twitter', values.get('Twitter'))
        user_name = values.get('Assigned User Name')
        if user_name and user_name in self.user_mapping:
            try:
                account.assigned_to = LilyUser.objects.get(
                    email=self.user_mapping[user_name],
                    tenant_id=self.tenant_pk
                )
            except LilyUser.DoesNotExist:
                if user_name not in self.already_logged:
                    self.already_logged.add(user_name)
                    logger.warning(u'Assignee does not exists as an LilyUser. %s' % user_name)
        else:
            # Only log when user_name not empty.
            if user_name and user_name not in self.already_logged:
                self.already_logged.add(user_name)
                logger.warning(u'Assignee does not have an usermapping. %s' % user_name)

        account.save()

    def _create_contact_data(self, values):
        """
        Create Contact instance for given dict.

        Arguments:
            values (dict):

        """
        if self.sugar_import:
            if not values.get('ID') or 30 > len(values.get('ID')) > 40:
                return

        column_attribute_mapping = {
            'ID': 'import_id',
            'First Name': 'first_name',
            '': 'preposition',
            'Last Name': 'last_name',
            '': 'gender',
            '': 'title',
            '': 'status',
            '': 'picture',
            'Description': 'description',
            '': 'salutation',
        }

        # Create contact
        contact_kwargs = dict()
        for column, value in values.items():
            if value and column in column_attribute_mapping:
                attribute = column_attribute_mapping.get(column)
                contact_kwargs[attribute] = value

        first, last = None, None
        if 'first_name' in contact_kwargs and contact_kwargs['first_name']:
            first = True
            contact_kwargs['first_name'] = contact_kwargs['first_name'][:254]
        if 'last_name' in contact_kwargs and contact_kwargs['last_name']:
            last = True
            contact_kwargs['last_name'] = contact_kwargs['last_name'][:254]

        if not (first or last):
            logger.warning(u'No first or last name for contact. %s' % contact_kwargs)
            return

        gender = 0
        if values.get('Salutation') in ['Mr.', 'Dhr.', 'mr.']:
            gender = 1
        elif values.get('Salutation') in ['Ms.', 'Mrs.']:
            gender = 2
        contact_kwargs['gender'] = gender

        contact_kwargs['tenant_id'] = self.tenant_pk
        try:
            contact = Contact.objects.get(tenant_id=self.tenant_pk, import_id=contact_kwargs['import_id'])
        except Contact.DoesNotExist:
            # Only check on name, if both first and last name exist:
            # Those were added before the import_id field was introduced.
            if first and last:
                try:
                    contact = Contact.objects.get(
                        tenant_id=self.tenant_pk,
                        first_name=contact_kwargs['first_name'],
                        last_name=contact_kwargs['last_name']
                    )
                except Contact.DoesNotExist:
                    contact = Contact(tenant_id=self.tenant_pk)
                except Contact.MultipleObjectsReturned:
                    logger.warning(u'Multiple contacts returned for %s' % contact_kwargs)
                    return
            else:
                contact = Contact(tenant_id=self.tenant_pk)

        for k, v in contact_kwargs.items():
            setattr(contact, k, v)

        contact.save()

        # Create addresses
        self._create_address(
            contact,
            'visiting',
            values.get('Primary Street'),
            values.get('Primary Postal Code'),
            values.get('Primary City'),
            values.get('Primary Country')
        )
        self._create_address(
            contact,
            'shipping',
            values.get('Alternate Street'),
            values.get('Alternate Postal Code'),
            values.get('Alternate City'),
            values.get('Alternate Country')
        )

        # Create email addresses
        self._create_email_addresses(contact, values)

        # Create phone numbers
        self._create_phone(contact, 'work', values.get('Office Phone'))
        self._create_phone(contact, 'work', values.get('Other Phone'))
        self._create_phone(contact, 'mobile', values.get('Mobile Phone'))
        self._create_phone(contact, 'other', values.get('Fax'), other_type='fax')
        self._create_phone(contact, 'other', values.get('Home Phone'), other_type='home')

        # Create social media
        self._create_social_media(contact, 'twitter', values.get('Twitter'))

        contact.save()

    def _create_address(self, instance, type, address, postal_code, city, country, primary=False):
        """
        Create an Address for given instance

        Arguments:
            instance (instance): instance to add Address to.
            type (str): kind of address
            address (str): street and number
            postal_code (str): postal code
            city (str): city
            country (str): country
        """
        if address and city:
            street, number, complement = parse_address(address)
            address_kwargs = dict()
            address_kwargs['type'] = type
            address_kwargs['street'] = street
            if _isint(number) and int(number) < 32766:
                address_kwargs['street_number'] = int(number)
            address_kwargs['complement'] = complement
            if len(postal_code) > 10:
                postal_code = postal_code[:10]
            address_kwargs['postal_code'] = postal_code
            address_kwargs['city'] = city
            if country:
                country = country.upper().strip()
                country = self.country_map.get(country, country)
                if country and len(country) > 2 or country not in self.country_codes:
                    country = ''
                    address_kwargs['country'] = country
            address_kwargs['tenant_id'] = self.tenant_pk
            if not instance.addresses.filter(
                    street=address_kwargs['street'],
                    city=address_kwargs['city']
            ).exists():
                try:
                    address = Address.objects.create(**address_kwargs)
                except DataError:
                    logger.warning('could not create address: %s' % address_kwargs)
                else:
                    instance.addresses.add(address)
            else:
                address_kwargs.pop('tenant_id')
                instance.addresses.filter(
                    street=address_kwargs['street'],
                    city=address_kwargs['city']
                ).update(**address_kwargs)

    def _create_email_addresses(self, instance, values):
        """
        Creates EmailAddresses for given instance

        Arguments:
            instance (instance): instance to add EmailAddresses to
            values (dict): dict of email address info
        """
        emails = list()
        emails.append((values.get('Email Address'), True))
        non_primary_emails = values.get('Non Primary E-mails')
        if non_primary_emails:
            for email in non_primary_emails.split(';'):
                emails.append((email, False))

        for email, is_primary in emails:
            self._create_email_address(instance, email, is_primary)

    def _create_email_address(self, instance, email, is_primary=True):
        """
        Creates EmailAddress for given instance

        Arguments:
            instance (instance): instance to add EmailAddress to
            email (str): string with email address
            is_primary (boolean): True if emailaddress is the primary
                email address for instance
        """
        if email and len(email) > 2:
            email_address_kwargs = dict()
            email_address_kwargs['email_address'] = email
            email_address_kwargs['is_primary'] = is_primary
            email_address_kwargs['tenant_id'] = self.tenant_pk
            if not instance.email_addresses.filter(**email_address_kwargs).exists():
                email_address = EmailAddress.objects.create(**email_address_kwargs)
                instance.email_addresses.add(email_address)

    def _create_phone(self, instance, type, raw_input, other_type=None):
        """
        Creates PhoneNumber for given instance

        Arguments:
            instance (instance): instance to add PhoneNumber to
            type (str): kind of phone number
            raw_input (str): unformatted phone number
            other_type (str) optional: given if not default phone number type
        """
        if raw_input and len(raw_input) > 2:
            phone_kwargs = dict()
            phone_kwargs['type'] = type
            phone_kwargs['other_type'] = other_type
            phone_kwargs['raw_input'] = raw_input
            phone_kwargs['tenant_id'] = self.tenant_pk
            if not instance.phone_numbers.filter(**phone_kwargs).exists():
                phone_number = PhoneNumber.objects.create(**phone_kwargs)
                instance.phone_numbers.add(phone_number)

    def _create_social_media(self, instance, name, username):
        """
        Create a SocialMedia instance for given instance

        Arguments:
            instance (instance): instance to add SocialMedia to
            name (str): name of social media network
            username (str): profile name on the network
        """
        if username and len(username) < 100:
            if username.startswith('/'):
                username = username[1:]
            if not username:
                return
            if not instance.social_media.filter(name=name, username=username).exists():
                sm = SocialMedia.objects.create(tenant_id=self.tenant_pk,
                                                name=name,
                                                username=username)
                instance.social_media.add(sm)

    def _create_website(self, account, url):
        """
        Add Website instance to given account

        Arguments:
            account (instance): Account to add Website to.
            url (str): url of website
        """
        if url and len(url) > 2 and url != 'http://':
            website_kwargs = dict()
            website_kwargs['tenant_id'] = self.tenant_pk
            website_kwargs['website'] = url
            website_kwargs['account'] = account
            website_kwargs['is_primary'] = True
            Website.objects.get_or_create(**website_kwargs)
