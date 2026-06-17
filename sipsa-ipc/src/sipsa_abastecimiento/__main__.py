"""Punto de entrada — permite ejecutar: python -m sipsa_abastecimiento."""
from pathlib import Path

from kedro.framework.project import configure_project
from kedro.framework.session import KedroSession


def main() -> None:
    configure_project("sipsa_abastecimiento")
    with KedroSession.create(project_path=Path.cwd()) as session:
        session.run()


if __name__ == "__main__":
    main()
