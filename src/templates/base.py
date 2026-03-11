"""
Base template class and template registry.

This module provides the abstract base class for dashboard templates
and a registry for template lookup by name.
"""

from abc import ABC, abstractmethod
from typing import Any, Optional, Type

from src.models.blueprint import ComponentConfig, ComponentType, DashboardBlueprint


class BaseTemplate(ABC):
    """
    Abstract base class for dashboard templates.
    """
    
    @classmethod
    @abstractmethod
    def get_name(cls) -> str:
        pass
    
    @classmethod
    @abstractmethod
    def get_description(cls) -> str:
        pass
    
    @abstractmethod
    def generate(
        self,
        session_id: str,
        title: str,
        data_summary: dict[str, Any],
        objective: Optional[str] = None,
    ) -> DashboardBlueprint:
        pass
    
    def _create_header(self, title: str) -> list[ComponentConfig]:
        """
        Create standard header components.
        """
        from datetime import datetime
        
        return [
            ComponentConfig(
                type=ComponentType.ROW,
                class_name="mb-4",
                children=[
                    ComponentConfig(
                        type=ComponentType.COLUMN,
                        props={"width": 12},
                        children=[
                            ComponentConfig(
                                type=ComponentType.H1,
                                props={"text": title},
                                class_name="display-5 fw-bold text-primary",
                            ),
                            ComponentConfig(
                                type=ComponentType.P,
                                props={
                                    "text": f"Generated on {datetime.now().strftime('%B %d, %Y at %H:%M')}"
                                },
                                class_name="text-muted",
                            ),
                        ],
                    ),
                ],
            ),
        ]
    
    def _create_kpi_row(
        self,
        kpis: list[dict[str, Any]],
        max_kpis: int = 4,
    ) -> ComponentConfig:
        kpis = kpis[:max_kpis]
        col_width = 12 // len(kpis) if kpis else 12
        
        children = []
        for i, kpi_data in enumerate(kpis):
            # Extract query if present
            query = kpi_data.pop("data_query", None) or kpi_data.pop("_data_query", None)
            children.append(
                ComponentConfig(
                    type=ComponentType.COLUMN,
                    props={"width": col_width},
                    children=[
                        ComponentConfig(
                            type=ComponentType.KPI_CARD,
                            props=kpi_data,
                            data_query=query,
                            id=f"kpi-{i}",
                        ),
                    ],
                )
            )
        
        return ComponentConfig(
            type=ComponentType.ROW,
            class_name="mb-4 g-3",
            children=children,
        )


# Template registry
_template_registry: dict[str, Type[BaseTemplate]] = {}


def register_template(template_class: Type[BaseTemplate]) -> Type[BaseTemplate]:
    name = template_class.get_name()
    _template_registry[name] = template_class
    return template_class


def get_template(name: str) -> Optional[BaseTemplate]:
    template_class = _template_registry.get(name)
    if template_class:
        return template_class()
    return None


def list_templates() -> list[dict[str, str]]:
    return [
        {
            "name": name,
            "description": cls.get_description(),
        }
        for name, cls in _template_registry.items()
    ]
