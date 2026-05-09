# Backfill the new `participants` M2M from the existing user_a / user_b
# columns so legacy DM conversations show up correctly under the new
# "is_participant via M2M" code path.
from django.db import migrations


def forwards(apps, schema_editor):
    Conversation = apps.get_model("messaging", "Conversation")
    for conv in Conversation.objects.filter(is_group=False).iterator():
        if conv.user_a_id and conv.user_b_id:
            conv.participants.add(conv.user_a_id, conv.user_b_id)


def backwards(apps, schema_editor):
    # No-op — leaving the M2M populated is harmless.
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('messaging', '0002_remove_conversation_unique_conv_pair_and_more'),
    ]

    operations = [
        migrations.RunPython(forwards, backwards),
    ]
