# djacoupche
Django applications coupling checker (within concrete project)

How to use:

1) activate virtual environment used by project that you want to inspect
2) install utility:
    $ pip install git+https://github.com/belyak/djacoupche.git
3) run utility in interactive mode:
    $ djacoupche --interactive

    After that you'll be asked for two paths: project settings module and project base directory. Please specify the first
as a path to the settings python file and the second as the path to the project root. You can use both relative and
absolute paths:

    

