"""Report project folder manager.

Each report project owns its Word template, Excel workbook, section config,
generated documents, and run logs under one project directory.
"""
import shutil
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml

from core.observability import get_logger

logger = get_logger(__name__)


@dataclass(frozen=True)
class ReportProject:
    """Resolved report project assets."""

    name: str
    slug: str
    project_dir: Path
    word_template_path: Path
    excel_workbook_path: Path
    section_config_path: Path
    output_dir: Path
    run_log_dir: Path
    prompt_templates_path: Optional[Path] = None
    data_source_paths: List[Path] = field(default_factory=list)
    generated_reports: List[Path] = field(default_factory=list)
    config: Dict[str, Any] = field(default_factory=dict)


class ReportProjectManager:
    """Read and bootstrap report project folders."""

    def __init__(self, projects_root: Optional[Path] = None):
        self.projects_root = (
            projects_root or Path(__file__).resolve().parents[2] / "report_projects"
        )
        self.projects_root.mkdir(parents=True, exist_ok=True)
        logger.info("ReportProjectManager initialized", projects_root=str(self.projects_root))

    def list_projects(self) -> List[ReportProject]:
        """List report projects with resolved asset paths."""
        projects: List[ReportProject] = []
        try:
            for project_dir in sorted(self.projects_root.iterdir(), key=lambda p: p.name):
                if not project_dir.is_dir():
                    continue
                project_yaml = project_dir / "project.yaml"
                if not project_yaml.exists():
                    logger.warning(
                        "Skipping report project without project.yaml", path=str(project_dir)
                    )
                    continue
                try:
                    projects.append(self._load_project(project_dir))
                except Exception as exc:
                    logger.error(
                        "Failed to load report project",
                        project_dir=str(project_dir),
                        error=str(exc),
                        exc_info=True,
                    )
            return projects
        except Exception:
            logger.exception(
                "Failed to list report projects", projects_root=str(self.projects_root)
            )
            raise

    def get_project(self, slug: str) -> ReportProject:
        """Load one project by folder slug."""
        project_dir = self.projects_root / slug
        if not project_dir.exists():
            raise FileNotFoundError(f"Report project not found: {slug}")
        return self._load_project(project_dir)

    def rename_project(self, slug: str, new_name: str) -> ReportProject:
        """Rename a report project folder and update project.yaml."""
        project_dir = self.projects_root / slug
        if not project_dir.exists():
            raise FileNotFoundError(f"Report project not found: {slug}")

        new_slug = new_name.strip()
        if not new_slug or any(part in new_slug for part in ["/", "\\", ".."]):
            raise ValueError("Invalid report project name")

        target_dir = self.projects_root / new_slug
        if target_dir.exists() and target_dir != project_dir:
            raise FileExistsError(f"Report project already exists: {new_slug}")

        try:
            project_yaml = project_dir / "project.yaml"
            data = yaml.safe_load(project_yaml.read_text(encoding="utf-8")) or {}
            data["name"] = new_name
            project_yaml.write_text(
                yaml.safe_dump(data, allow_unicode=True, sort_keys=False),
                encoding="utf-8",
            )
            if target_dir != project_dir:
                project_dir.rename(target_dir)
            logger.info("Renamed report project", old_slug=slug, new_slug=new_slug)
            return self._load_project(target_dir)
        except Exception:
            logger.exception("Failed to rename report project", slug=slug, new_name=new_name)
            raise

    def bootstrap_cyb50_project(self, source_dir: Optional[Path] = None) -> ReportProject:
        """Create or refresh the default 创业板50 report project package."""
        source_dir = source_dir or Path(__file__).resolve().parents[2]
        project_dir = self.projects_root / "创业板50周报"
        templates_dir = project_dir / "templates"
        data_dir = project_dir / "data"
        config_dir = project_dir / "config"
        generated_dir = project_dir / "generated"
        runs_dir = project_dir / "runs"

        for directory in [templates_dir, data_dir, config_dir, generated_dir, runs_dir]:
            directory.mkdir(parents=True, exist_ok=True)

        copy_map = {
            source_dir / "创业板50周报模板.docx": templates_dir / "report_template.docx",
            source_dir / "创业板50周报（iFind版）.xlsx": data_dir / "创业板50周报（iFind版）.xlsx",
            source_dir / "创业板50周报（Wind版）.xlsx": data_dir / "创业板50周报（Wind版）.xlsx",
            source_dir / "创业板50周报模板.yaml": config_dir / "section_config.yaml",
        }

        try:
            for source, target in copy_map.items():
                if source.exists():
                    shutil.copy2(source, target)
                    logger.info(
                        "Copied report project asset", source=str(source), target=str(target)
                    )
                else:
                    logger.warning("Report project source asset missing", source=str(source))

            project_yaml = project_dir / "project.yaml"
            project_data = {
                "name": "创业板50周报",
                "active_word_template": "templates/report_template.docx",
                "active_excel_workbook": "data/创业板50周报（iFind版）.xlsx",
                "section_config": "config/section_config.yaml",
                "data_sources": [],
                "output_dir": "generated",
                "run_log_dir": "runs",
            }
            project_yaml.write_text(
                yaml.safe_dump(project_data, allow_unicode=True, sort_keys=False),
                encoding="utf-8",
            )
            logger.info("Bootstrapped report project", project_dir=str(project_dir))
            return self._load_project(project_dir)
        except Exception:
            logger.exception(
                "Failed to bootstrap CYB50 report project", project_dir=str(project_dir)
            )
            raise

    def _load_project(self, project_dir: Path) -> ReportProject:
        project_yaml = project_dir / "project.yaml"
        try:
            data = yaml.safe_load(project_yaml.read_text(encoding="utf-8")) or {}
        except yaml.YAMLError as exc:
            logger.error("Invalid report project YAML", path=str(project_yaml), error=str(exc))
            raise ValueError(f"Invalid report project YAML: {project_yaml}") from exc

        name = data.get("name") or project_dir.name
        word_template_path = self._resolve(project_dir, data.get("active_word_template"))
        excel_workbook_path = self._resolve(project_dir, data.get("active_excel_workbook"))
        section_config_path = self._resolve(project_dir, data.get("section_config"))
        output_dir = self._resolve(project_dir, data.get("output_dir", "generated"))
        run_log_dir = self._resolve(project_dir, data.get("run_log_dir", "runs"))
        prompt_templates_path = self._resolve_optional(project_dir, data.get("prompt_templates"))
        data_source_paths = [
            self._resolve(project_dir, source_path)
            for source_path in data.get("data_sources", [])
            if source_path
        ]

        for label, path in [
            ("active_word_template", word_template_path),
            ("section_config", section_config_path),
        ]:
            if not path.exists():
                raise FileNotFoundError(f"Report project asset missing: {label} -> {path}")
        if data.get("active_excel_workbook") and not excel_workbook_path.exists():
            raise FileNotFoundError(
                f"Report project asset missing: active_excel_workbook -> {excel_workbook_path}"
            )
        if prompt_templates_path and not prompt_templates_path.exists():
            raise FileNotFoundError(
                f"Report project asset missing: prompt_templates -> {prompt_templates_path}"
            )
        for path in data_source_paths:
            if not path.exists():
                raise FileNotFoundError(f"Report project asset missing: data_sources -> {path}")

        output_dir.mkdir(parents=True, exist_ok=True)
        run_log_dir.mkdir(parents=True, exist_ok=True)
        generated_reports = sorted(output_dir.glob("*.docx"), reverse=True)

        return ReportProject(
            name=name,
            slug=project_dir.name,
            project_dir=project_dir,
            word_template_path=word_template_path,
            excel_workbook_path=excel_workbook_path,
            section_config_path=section_config_path,
            output_dir=output_dir,
            run_log_dir=run_log_dir,
            prompt_templates_path=prompt_templates_path,
            data_source_paths=data_source_paths,
            generated_reports=generated_reports,
            config=data,
        )

    @staticmethod
    def _resolve(project_dir: Path, path_value: Optional[str]) -> Path:
        if not path_value:
            return project_dir
        path = Path(path_value)
        if path.is_absolute():
            return path
        return project_dir / path

    @staticmethod
    def _resolve_optional(project_dir: Path, path_value: Optional[str]) -> Optional[Path]:
        if not path_value:
            return None
        path = Path(path_value)
        if path.is_absolute():
            return path
        return project_dir / path
