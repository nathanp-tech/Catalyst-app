from django.db import migrations

def do_nothing(apps, schema_editor):
    """
    Cette migration ne fait plus rien. La population des données est
    maintenant gérée par la commande 'sync_curriculum'.
    """
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('documents', '0002_document_solution_for_alter_document_file_and_more'), 
    ]

    operations = [
        migrations.RunPython(do_nothing, reverse_code=do_nothing),
    ]
