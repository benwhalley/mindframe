# file: mindframe/management/commands/reembed_mindframe.py

"""
Functions to

- embed text in a document store
- extract chunks of the original text for RAG prompting

Examples:

"""

from django.core.management.base import BaseCommand
from mindframe.models import Memory, MemoryChunk


class Command(BaseCommand):
    help = "Re-embed all Memories."

    def handle(self, *args, **options):
        self.stdout.write("Starting re-embedding of Examples and Turns...")

        # Get all memories
        memories = Memory.objects.all()
        for i in memories:
            print(i)
            r = i.make_chunks()
            print(f"{len(r)} chunks created")
