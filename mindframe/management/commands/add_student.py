import shortuuid
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    help = "Create users from a comma-separated list of emails and add them to a specified group."

    def add_arguments(self, parser):
        parser.add_argument(
            "emails",
            type=str,
            help="Comma-separated list of email addresses.",
        )
        parser.add_argument(
            "--group",
            type=str,
            default="Project Students",
            help="Name of the group to add users to (default: 'Project Students').",
        )

    def handle(self, *args, **kwargs):
        emails = kwargs["emails"]
        group_name = kwargs["group"]

        # Split the emails string into a list
        email_list = [email.strip() for email in emails.split(",")]

        # Fetch the CustomUser model
        User = get_user_model()

        # Create the group if it doesn't exist
        group, created = Group.objects.get_or_create(name=group_name)
        if created:
            self.stdout.write(f"Group '{group_name}' created.")
        else:
            self.stdout.write(f"Group '{group_name}' already exists.")

        for email in email_list:
            try:
                # Split email into components
                username = email.split("@")[0]  # Part before "@"
                first_part, *middle, last_part = username.split(".")  # Split on "."
                first_name = first_part.capitalize()
                last_name = last_part.capitalize()

                # Generate a unique password
                password = shortuuid.uuid()

                # Create or get the user
                user, created = User.objects.get_or_create(
                    username=username,
                    defaults={
                        "email": email,
                        "first_name": first_name,
                        "last_name": last_name,
                        "is_staff": True,  # Mark user as staff
                    },
                )

                # Set password for new users
                if created:
                    user.set_password(password)
                    user.save()
                    self.stdout.write(f"Created user: Username: {username}, Password: {password}")
                else:
                    self.stdout.write(f"User {username} already exists.")

                # Add the user to the group
                user.groups.add(group)
                self.stdout.write(f"Added {username} to group '{group_name}'.")
            except Exception as e:
                raise CommandError(f"Failed to process email {email}: {e}")
