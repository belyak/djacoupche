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


def normalize_relative_imports(current_package, names):
    def normalize_relative_import(name):
        if name[0] == "." and name[1] != ".":
            return current_package + name
        else:
            return name

    return list(map(normalize_relative_import, names))


def get_module_imports(package_file, module_file):
    with open(module_file, 'rb') as f:
        module = ast.parse(source=f.read())

    module_imports = []
    for node in (n for n in module.body if n is not None):
        try:
            process_func = NODE_PROCESS_FUNCS[type(node)]
        except KeyError:
            continue

        result = process_func(node)
        normalized_result = normalize_relative_imports(current_package=os.path.basename(package_file), names=result)
        module_imports.extend(normalized_result)

    return module_imports


def get_package_imports(name):
    print("testing package (application)", name)
    files = [join(name, f) for f in listdir(name) if isfile(join(name, f)) and f.endswith('.py')]

    result = []
    for file in files:
        result.extend(
            get_module_imports(package_file=name, module_file=file)
        )
    return result


def get_custom_installed_apps(django_settings_module_path, project_root_path):
    with open(django_settings_module_path, "rb") as f:
        module = ast.parse(f.read())

    extracted_installed_apps = None
    """:type: list"""

    class AssignNodeVIsitor(ast.NodeVisitor):
        def visit_Assign(self, node):
            if len(node.targets) == 1 and node.targets[0].id == "INSTALLED_APPS":
                nonlocal extracted_installed_apps
                extracted_installed_apps = [n.s for n in node.value.elts]

            self.generic_visit(node)

    AssignNodeVIsitor().visit(module)

    if extracted_installed_apps is None:
        raise ValueError("Cannot find INSTALLED_APPS in file %s!" % django_settings_module_path)

    possible_packages = [join(project_root_path, *app_dir.split(".")) for app_dir in extracted_installed_apps]
    return [p for p in possible_packages if os.path.exists(p)]


def populate_modules_and_imports_structure(custom_installed_apps_dirs):
    modules_and_imports = {}
    for module_path in custom_installed_apps_dirs:
        module_name = os.path.basename(module_path)
        modules_and_imports[module_name] = get_package_imports(module_path)
    return modules_and_imports


def remove_non_project_imports(modules_and_imports, custom_installed_apps):
    for module, imports, in modules_and_imports.items():
        modules_and_imports[module] = [i for i in imports if i.split(".")[0] in custom_installed_apps]
    return modules_and_imports


def perform_detection(django_settings_module_path, project_root_path):
    custom_installed_apps_dirs = get_custom_installed_apps(django_settings_module_path, project_root_path)
    custom_installed_apps = [os.path.basename(p) for p in custom_installed_apps_dirs]

    modules_and_imports = populate_modules_and_imports_structure(custom_installed_apps_dirs)
    modules_and_imports = remove_non_project_imports(modules_and_imports, custom_installed_apps)

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


def djacoupche():
    django_settings_module = input(
        "Enter the path to the django settings module of the project (where INSTALLED_APPS can be found):"
    )
    project_root = input("Enter the path to the project root (where manage.py is located):")
    perform_detection(django_settings_module, project_root)


if __name__ == '__main__':
    djacoupche()
