# -*- coding: utf-8 -*-
# Generated by Django 1.11.15 on 2018-10-16 09:28
from __future__ import unicode_literals

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('email', '0045_add_email_body_model'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='emailmessage',
            name='body_html',
        ),
    ]
