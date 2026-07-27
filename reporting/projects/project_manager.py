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
    report_config_path: Path
    output_dir: Path
    run_log_dir: Path
    prompt_templates_path: Optional[Path] = None
    data_source_paths: List[Path] = field(default_factory=list)
    generated_reports: List[Path] = field(default_factory=list)
    config: Dict[str, Any] = field(default_factory=dict)
    project_type: str = "word"
    ppt_template_path: Optional[Path] = None
    template_path: Optional[Path] = None


@dataclass(frozen=True)
class ReportProjectScanIssue:
    """A non-fatal problem found while scanning a report project folder."""

    code: str
    project_slug: str
    relative_path: str


@dataclass(frozen=True)
class ReportProjectScanResult:
    """Report projects and non-fatal scan issues."""

    projects: List[ReportProject] = field(default_factory=list)
    issues: List[ReportProjectScanIssue] = field(default_factory=list)


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
        return self.scan_projects().projects

    def scan_projects(self) -> ReportProjectScanResult:
        """Scan report projects while preserving non-fatal asset diagnostics."""
        projects: List[ReportProject] = []
        issues: List[ReportProjectScanIssue] = []
        try:
            for project_dir in sorted(self.projects_root.iterdir(), key=lambda p: p.name):
                if not project_dir.is_dir():
                    continue
                project_yaml = project_dir / "project.yaml"
                if not project_yaml.exists():
                    logger.debug(
                        "Ignoring report project directory without project.yaml",
                        path=str(project_dir),
                    )
                    continue
                try:
                    projects.append(self._load_project(project_dir))
                except Exception as exc:
                    issue = self._build_scan_issue(project_dir, exc)
                    issues.append(issue)
                    logger.error(
                        "Failed to load report project",
                        project_dir=str(project_dir),
                        error=str(exc),
                        exc_info=True,
                    )
            return ReportProjectScanResult(projects=projects, issues=issues)
        except Exception:
            logger.exception(
                "Failed to scan report projects", projects_root=str(self.projects_root)
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
            source_dir / "创业板50周报模板.yaml": config_dir / "report_config.yaml",
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
                "report_config": "config/report_config.yaml",
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

    @staticmethod
    def _validate_project_asset_paths(project_dir: Path, data: Dict[str, Any]) -> None:
        """Reject project configuration paths that leave the project directory."""
        path_values = [
            data.get("active_word_template"),
            data.get("active_ppt_template"),
            data.get("active_excel_workbook"),
            data.get("report_config"),
            data.get("output_dir", "generated"),
            data.get("run_log_dir", "runs"),
            data.get("prompt_templates"),
            *data.get("data_sources", []),
        ]
        root = project_dir.resolve()
        for path_value in path_values:
            if not path_value:
                continue
            path = Path(path_value)
            candidate = path.resolve() if path.is_absolute() else (root / path).resolve()
            try:
                candidate.relative_to(root)
            except ValueError as exc:
                raise ValueError("Report project asset path is outside project directory") from exc

    @staticmethod
    def _build_scan_issue(project_dir: Path, exc: Exception) -> ReportProjectScanIssue:
        """Convert a loading failure into a stable, frontend-safe diagnostic."""
        if isinstance(exc, yaml.YAMLError) or "Invalid report project YAML" in str(exc):
            return ReportProjectScanIssue(
                code="invalid_project_yaml",
                project_slug=project_dir.name,
                relative_path="project.yaml",
            )

        message = str(exc)
        if message == "Report project asset path is outside project directory":
            return ReportProjectScanIssue(
                code="external_asset",
                project_slug=project_dir.name,
                relative_path="external_asset",
            )
        asset_prefix = "Report project asset missing: "
        if message.startswith(asset_prefix):
            label_and_path = message[len(asset_prefix) :]
            label, _, path_text = label_and_path.partition(" -> ")
            path = Path(path_text)
            try:
                relative_path = str(path.relative_to(project_dir))
            except ValueError:
                relative_path = path.name
            issue_code = {
                "active_word_template": "missing_active_word_template",
                "active_ppt_template": "missing_active_ppt_template",
                "report_config": "missing_report_config",
            }.get(label, "missing_project_asset")
            return ReportProjectScanIssue(
                code=issue_code,
                project_slug=project_dir.name,
                relative_path=relative_path,
            )

        return ReportProjectScanIssue(
            code="unreadable_project",
            project_slug=project_dir.name,
            relative_path="project.yaml",
        )

    def _load_project(self, project_dir: Path) -> ReportProject:
        project_yaml = project_dir / "project.yaml"
        try:
            data = yaml.safe_load(project_yaml.read_text(encoding="utf-8")) or {}
        except yaml.YAMLError as exc:
            logger.error("Invalid report project YAML", path=str(project_yaml), error=str(exc))
            raise ValueError(f"Invalid report project YAML: {project_yaml}") from exc

        name = data.get("name") or project_dir.name
        project_type = str(data.get("project_type") or "word").strip().lower()
        if project_type not in {"word", "ppt"}:
            raise ValueError(f"Unsupported report project type: {project_type}")

        self._validate_project_asset_paths(project_dir, data)
        word_template_path = self._resolve(project_dir, data.get("active_word_template"))
        ppt_template_path = self._resolve_optional(project_dir, data.get("active_ppt_template"))
        template_path = ppt_template_path if project_type == "ppt" else word_template_path
        excel_workbook_path = self._resolve(project_dir, data.get("active_excel_workbook"))
        report_config_path = self._resolve(project_dir, data.get("report_config"))
        output_dir = self._resolve(project_dir, data.get("output_dir", "generated"))
        run_log_dir = self._resolve(project_dir, data.get("run_log_dir", "runs"))
        prompt_templates_path = self._resolve_optional(project_dir, data.get("prompt_templates"))
        data_source_paths = [
            self._resolve(project_dir, source_path)
            for source_path in data.get("data_sources", [])
            if source_path
        ]

        required_assets = [("report_config", report_config_path)]
        if project_type == "ppt":
            if not ppt_template_path:
                raise FileNotFoundError(
                    f"Report project asset missing: active_ppt_template -> {project_dir}"
                )
            required_assets.append(("active_ppt_template", ppt_template_path))
        else:
            required_assets.append(("active_word_template", word_template_path))

        for label, path in required_assets:
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
        output_pattern = "*.pptx" if project_type == "ppt" else "*.docx"
        generated_reports = sorted(output_dir.glob(output_pattern), reverse=True)

        return ReportProject(
            name=name,
            slug=project_dir.name,
            project_dir=project_dir,
            word_template_path=word_template_path,
            excel_workbook_path=excel_workbook_path,
            report_config_path=report_config_path,
            output_dir=output_dir,
            run_log_dir=run_log_dir,
            prompt_templates_path=prompt_templates_path,
            data_source_paths=data_source_paths,
            generated_reports=generated_reports,
            config=data,
            project_type=project_type,
            ppt_template_path=ppt_template_path,
            template_path=template_path,
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
