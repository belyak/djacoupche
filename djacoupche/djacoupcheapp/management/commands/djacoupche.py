from django.conf import settings
from django.core.management import BaseCommand

from djacoupche.django_apps_coupling_checker import Detector, filter_custom_installed_apps


class DjangoIntegratedDetector(Detector):
    def get_custom_installed_apps(self):
        return filter_custom_installed_apps(settings.INSTALLED_APPS, self.project_root_path)


class Command(BaseCommand):
    help = 'analyzes django apps dependencies using djacoupche utility'

    def handle(self, *args, **options):
        detector = DjangoIntegratedDetector(django_settings_module_path=None,
                                            project_root_path=str(settings.ROOT_DIR))
        detector.preform_detection()