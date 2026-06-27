from django.db import migrations, models
import django.db.models.deletion
import django.utils.timezone


def migrate_to_touches(apps, schema_editor):
    Campaign = apps.get_model("campaigns", "Campaign")
    Contact = apps.get_model("campaigns", "Contact")
    Touch = apps.get_model("campaigns", "Touch")
    ContactSend = apps.get_model("campaigns", "ContactSend")

    for campaign in Campaign.objects.all():
        touch = Touch.objects.create(
            campaign=campaign,
            order=1,
            label=campaign.label,
            subject=campaign.subject,
            body_template=campaign.body_template,
            status=campaign.status,
            sent_count=campaign.sent_count,
            failed_count=campaign.failed_count,
            total_contacts=campaign.total_contacts,
        )

        seen_emails = set()
        for contact in Contact.objects.filter(campaign=campaign).order_by("created_at"):
            contact.account = campaign.account
            contact.save(update_fields=["account"])

            if contact.email in seen_emails:
                continue
            seen_emails.add(contact.email)

            send_status = contact.status if contact.status in ("sent", "failed") else "pending"
            ContactSend.objects.create(
                touch=touch,
                contact=contact,
                status=send_status,
                sent_at=contact.sent_at if contact.status == "sent" else None,
                error_message=contact.error_message if contact.status == "failed" else "",
            )


def reverse_migrate(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ("campaigns", "0001_initial"),
        ("accounts", "0001_initial"),
    ]

    operations = [
        migrations.CreateModel(
            name="Touch",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(db_index=True, default=django.utils.timezone.now)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("order", models.PositiveIntegerField()),
                ("label", models.CharField(max_length=255)),
                ("subject", models.TextField()),
                ("body_template", models.TextField()),
                ("status", models.CharField(
                    choices=[("pending", "Pending"), ("running", "Running"), ("completed", "Completed"), ("failed", "Failed")],
                    default="pending",
                    max_length=20,
                )),
                ("sent_count", models.IntegerField(default=0)),
                ("failed_count", models.IntegerField(default=0)),
                ("total_contacts", models.IntegerField(default=0)),
                ("campaign", models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name="touches",
                    to="campaigns.campaign",
                )),
            ],
            options={
                "ordering": ["order"],
                "unique_together": {("campaign", "order")},
            },
        ),
        migrations.CreateModel(
            name="ContactSend",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(db_index=True, default=django.utils.timezone.now)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("status", models.CharField(
                    choices=[("pending", "Pending"), ("sent", "Sent"), ("failed", "Failed"), ("skipped", "Skipped")],
                    default="pending",
                    max_length=20,
                )),
                ("sent_at", models.DateTimeField(blank=True, null=True)),
                ("error_message", models.TextField(blank=True)),
                ("gmail_message_id", models.CharField(blank=True, max_length=255)),
                ("gmail_thread_id", models.CharField(blank=True, max_length=255)),
                ("contact", models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name="sends",
                    to="campaigns.contact",
                )),
                ("touch", models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name="contact_sends",
                    to="campaigns.touch",
                )),
            ],
            options={
                "ordering": ["created_at"],
                "unique_together": {("touch", "contact")},
            },
        ),
        migrations.CreateModel(
            name="Blacklist",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(db_index=True, default=django.utils.timezone.now)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("email", models.EmailField(unique=True)),
                ("reason", models.TextField(blank=True)),
            ],
            options={
                "ordering": ["email"],
            },
        ),
        migrations.AddField(
            model_name="contact",
            name="account",
            field=models.ForeignKey(
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="contacts",
                to="accounts.googleaccount",
            ),
        ),
        migrations.RunPython(migrate_to_touches, reverse_migrate),
        migrations.AlterField(
            model_name="contact",
            name="account",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.PROTECT,
                related_name="contacts",
                to="accounts.googleaccount",
            ),
        ),
        migrations.AlterUniqueTogether(
            name="contact",
            unique_together={("account", "email")},
        ),
        migrations.RemoveField(model_name="campaign", name="subject"),
        migrations.RemoveField(model_name="campaign", name="label"),
        migrations.RemoveField(model_name="campaign", name="body_template"),
        migrations.RemoveField(model_name="campaign", name="sent_count"),
        migrations.RemoveField(model_name="campaign", name="failed_count"),
        migrations.RemoveField(model_name="contact", name="status"),
        migrations.RemoveField(model_name="contact", name="sent_at"),
        migrations.RemoveField(model_name="contact", name="error_message"),
    ]
