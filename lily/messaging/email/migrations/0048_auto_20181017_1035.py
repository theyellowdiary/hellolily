# -*- coding: utf-8 -*-
# Generated by Django 1.11.15 on 2018-10-17 10:35
from __future__ import unicode_literals

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('email', '0047_auto_20181016_0929'),
    ]

    operations = [
        migrations.RenameField(
            model_name='emailmessage',
            old_name='body_html',
            new_name='body_html_fk',
        ),
    ]
