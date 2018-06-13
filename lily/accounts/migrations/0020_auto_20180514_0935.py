# -*- coding: utf-8 -*-
# Generated by Django 1.11.11 on 2018-05-14 09:35
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0019_auto_20170419_0926'),
    ]

    operations = [
        migrations.AlterField(
            model_name='account',
            name='addresses',
            field=models.ManyToManyField(blank=True, to='utils.Address', verbose_name='list of addresses'),
        ),
        migrations.AlterField(
            model_name='account',
            name='email_addresses',
            field=models.ManyToManyField(blank=True, to='utils.EmailAddress', verbose_name='list of email addresses'),
        ),
        migrations.AlterField(
            model_name='account',
            name='phone_numbers',
            field=models.ManyToManyField(blank=True, to='utils.PhoneNumber', verbose_name='list of phone numbers'),
        ),
    ]
