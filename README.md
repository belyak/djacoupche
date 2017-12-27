## DJACoupChe - Django Applications Coupling Checker
DJACoupChe can detect bi-directional django packages dependencies. For example: given applications A and B; A has dependencies inside B package and B has dependencies inside A. Even if such a situation does not cause cyclic imports, it should be considered as a decomposition/design defect.



How to use:

1) activate virtual environment used by project that you want to inspect.
    ```
    $ source <virtual environment directory>/bin/activate
    ```

2) install djacoupche:
    ```
    $ pip install git+https://github.com/belyak/djacoupche.git
    ```
    
3) run utility in interactive mode:
    ```
    $ djacoupche --interactive
    ```
    After that you'll be asked for two paths: project settings module and project base directory. Please specify the first
as a path to the settings python file and the second as the path to the project root. You can use both relative and
absolute paths.

4) run utility from project directory and using --django_settings key:
    ```
    $ djacoupche --django_settings=config/settings/base.py
    ```
    In that case no additional input is required.


