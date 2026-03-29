from django.core.management.base import BaseCommand
from irrigation.utils.json_loader import JSONIntentLoader
import json
import os
from django.conf import settings


class Command(BaseCommand):
    help = 'Manage chatbot JSON intents'

    def add_arguments(self, parser):
        parser.add_argument(
            '--reload',
            action='store_true',
            help='Reload all JSON intents from files'
        )
        parser.add_argument(
            '--list',
            action='store_true',
            help='List all loaded intents'
        )
        parser.add_argument(
            '--export',
            type=str,
            help='Export intents to a JSON file'
        )

    def handle(self, *args, **options):
        loader = JSONIntentLoader()

        if options['reload']:
            loader.reload_intents()
            self.stdout.write(
                self.style.SUCCESS('Successfully reloaded all JSON intents')
            )

        if options['list']:
            intents = loader.get_all_intents()
            for category, data in intents.items():
                self.stdout.write(
                    self.style.SUCCESS(f'{category.upper()}: {len(data.get("intents", []))} intents')
                )
                for intent in data.get('intents', []):
                    self.stdout.write(f"  - {intent['tag']}: {len(intent['patterns'])} patterns")

        if options['export']:
            export_path = options['export']
            intents = loader.get_all_intents()
            with open(export_path, 'w', encoding='utf-8') as f:
                json.dump(intents, f, indent=2, ensure_ascii=False)
            self.stdout.write(
                self.style.SUCCESS(f'Successfully exported intents to {export_path}')
            )
