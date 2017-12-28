import argparse
import ast
import os
from os import listdir
from os.path import isfile, join

import itertools

from collections import defaultdict


def process_import(node: ast.Import):
    return [name.name for name in node.names]


def process_import_from(node: ast.ImportFrom):
    start = "." * node.level

    if node.module is not None:
        start += node.module + "."

    return [start + name.name for name in node.names]


NODE_PROCESS_FUNCS = {
    ast.Import: process_import,
    ast.ImportFrom: process_import_from,
}


def load_ast_module(module_path):
    with open(module_path, "rb") as f:
        return ast.parse(f.read())


def normalize_relative_imports(packages, names):
    def normalize_relative_import(name: str):
        leading_dots_count = len(name) - len(name.lstrip("."))

        if leading_dots_count != 0:
            return ".".join(packages[:len(packages) - leading_dots_count + 1]) + "." + name.lstrip(".")
        else:
            return name

    return list(map(normalize_relative_import, names))


def get_packages(project_base, package_file):
    _project_base, _package_file = os.path.abspath(project_base), os.path.abspath(package_file)
    packages_path = _package_file[len(_project_base):].lstrip(os.path.sep)
    return packages_path.split(os.path.sep)


def get_module_imports(project_base, package_file, module_file):
    with open(module_file, 'rb') as f:
        module = ast.parse(source=f.read())

    module_imports = []
    for node in (n for n in module.body if n is not None):
        try:
            process_func = NODE_PROCESS_FUNCS[type(node)]
        except KeyError:
            continue

        result = process_func(node)
        normalized_result = normalize_relative_imports(packages=get_packages(project_base, package_file), names=result)
        module_imports.extend(normalized_result)

    return module_imports


def get_package_imports(project_base, name):
    print("collecting imports from application {application}".format(application=name))
    files = [join(name, f) for f in listdir(name) if isfile(join(name, f)) and f.endswith('.py')]

    result = []
    for file in files:
        result.extend(
            get_module_imports(project_base=project_base, package_file=name, module_file=file)
        )
    return result


def get_installed_apps_using_ast(ast_module):

    class AssignNodeVisitor(ast.NodeVisitor):
        def __init__(self):
            super().__init__()
            self.installed_apps = []

        def visit_Assign(self, node):
            if len(node.targets) == 1:
                target_node = node.targets[0]

                if isinstance(target_node, ast.Name) and target_node.id == "INSTALLED_APPS":
                    if isinstance(node.value, ast.List):
                        self.installed_apps = [n.s for n in node.value.elts]

            self.generic_visit(node)

    visitor = AssignNodeVisitor()
    visitor.visit(ast_module)

    return visitor.installed_apps


def get_installed_apps_using_ast_evaluation(ast_module):
    namespace = globals()
    co = compile(ast_module, "<ast>", "exec")
    exec(co, namespace)
    return namespace.get('INSTALLED_APPS', None)


def get_custom_installed_apps(django_settings_module_path, project_root_path):
    ast_module = load_ast_module(django_settings_module_path)

    extracted_installed_apps = (get_installed_apps_using_ast(ast_module) or
                                get_installed_apps_using_ast_evaluation(ast_module))

    if extracted_installed_apps is None:
        raise ValueError("Cannot find INSTALLED_APPS in file %s!" % django_settings_module_path)

    return filter_custom_installed_apps(extracted_installed_apps, project_root_path)


def filter_custom_installed_apps(extracted_installed_apps, project_root_path):
    possible_packages = [join(project_root_path, *app.split(".")) for app in extracted_installed_apps]
    return [p for p in possible_packages if os.path.exists(p)]


def populate_modules_and_imports_structure(project_base, custom_installed_apps_dirs):
    modules_and_imports = {}
    for module_path in custom_installed_apps_dirs:
        module_name = ".".join(get_packages(project_base, module_path))
        modules_and_imports[module_name] = get_package_imports(project_base, module_path)
    return modules_and_imports


def remove_non_project_imports(modules_and_imports, custom_installed_apps):
    def include_import(i):
        return any(i.startswith(app) for app in custom_installed_apps)

    for module, imports, in modules_and_imports.items():
        modules_and_imports[module] = [i for i in imports if include_import(i)]

    return modules_and_imports


class Detector:
    def __init__(self, django_settings_module_path, project_root_path):
        self.django_settings_module_path = django_settings_module_path
        self.project_root_path = project_root_path

    def preform_detection(self):
        modules_and_imports = self.collect_data()
        self.analyze(modules_and_imports)

    def collect_data(self):
        custom_installed_apps_dirs = self.get_custom_installed_apps()

        custom_installed_apps = []
        for custom_installed_app_dir in custom_installed_apps_dirs:
            custom_installed_apps.append(".".join(get_packages(self.project_root_path, custom_installed_app_dir)))

        modules_and_imports = populate_modules_and_imports_structure(self.project_root_path, custom_installed_apps_dirs)
        return remove_non_project_imports(modules_and_imports, custom_installed_apps)

    def analyze(self, modules_and_imports):
        def module_depends_on_another(module_name, another_module_name):
            """checks if module_name has dependency another_module_name (imports from it)"""
            for i in modules_and_imports[module_name]:
                if i.startswith(another_module_name):
                    return True
            return False

        product = set((a, b,) for (a, b,) in itertools.product(modules_and_imports.keys(), repeat=2) if a != b)
        processed_pairs = set()

        applications_dependencies = defaultdict(list)

        pairs_with_bidirectional_dependencies = []

        print("*" * 40)
        print("Applications dependencies analysis: ", end='')

        for module_a, module_b, in product:
            if (module_a, module_b) in processed_pairs:
                continue

            a_depends_on_b = module_depends_on_another(module_a, module_b)
            b_depends_on_a = module_depends_on_another(module_b, module_a)

            if a_depends_on_b and b_depends_on_a:
                pairs_with_bidirectional_dependencies.append((module_a, module_b))
            elif a_depends_on_b:
                applications_dependencies[module_a].append(module_b)
            elif b_depends_on_a:
                applications_dependencies[module_b].append(module_a)

            processed_pairs.update([(module_a, module_b), (module_b, module_a)])

        print("complete.")
        print("*" * 40)
        print("Application dependencies summary:", "\n")
        for application, deps, in applications_dependencies.items():
            print("%s depends on %s" % (application, ", ".join(deps) if deps else "[]"))

        print()
        print("*" * 40)
        if len(pairs_with_bidirectional_dependencies):
            print("Problems (bidirectional dependencies):", "\n")
            for m1, m2, in pairs_with_bidirectional_dependencies:
                text = "*** WARNING: bidirectional dependencies between %s AND %s" % (m1, m2)
                print(text)
        else:
            print("No problems with bidirectional dependencies detected.")

    def get_custom_installed_apps(self):
        return get_custom_installed_apps(self.django_settings_module_path, self.project_root_path)


def perform_detection_with_manual_input():
    django_settings_module = input(
        "Enter the path to the django settings module of the project (where INSTALLED_APPS can be found):"
    )
    project_root = input("Enter the path to the project root (where manage.py is located):")
    Detector(django_settings_module, project_root).preform_detection()


def parse_cmd_arguments():
    parser = argparse.ArgumentParser()

    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument('--django_settings', metavar='django_settings', type=argparse.FileType(), nargs=1,
                       help='path to the django settings file (containing INSTALLED_APPS)')
    group.add_argument('--interactive', action='store_true',
                       help='start utility and ask user all the required parameters.')

    parser.add_argument('--project_root', metavar="project_base", type=str, default=".", nargs='?',
                        help='the root directory for the project (manage.py located there usually)')

    return parser.parse_args()


def djacoupche():
    args_namespace = parse_cmd_arguments()

    if args_namespace.interactive:
        perform_detection_with_manual_input()
    else:
        detector = Detector(django_settings_module_path=args_namespace.django_settings[0].name,
                            project_root_path=args_namespace.project_root)
        detector.preform_detection()


if __name__ == '__main__':
    djacoupche()
