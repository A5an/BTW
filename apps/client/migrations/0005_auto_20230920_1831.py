# Generated by Django 3.1.7 on 2023-09-20 12:31

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('client', '0004_auto_20230920_1828'),
    ]

    operations = [
        migrations.AlterField(
            model_name='lobby',
            name='created',
            field=models.DateTimeField(auto_now_add=True),
        ),
    ]
