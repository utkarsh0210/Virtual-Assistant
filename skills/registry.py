# """
# skills/registry.py — Skill Plugin Registry
# Auto-discovers and registers skill plugins from the skills/ directory.
# """

# import importlib
# import logging
# from typing import Any, Dict, List, Optional

# logger = logging.getLogger("bharvishya.registry")


# class BaseSkill:
#     """
#     Abstract base class for all Bharvishya skill plugins.

#     Subclass this, define `name`, `description`, and implement `execute()`.
#     """
#     name: str = ""
#     description: str = ""
#     actions: List[str] = []

#     async def execute(self, action: str, params: Dict[str, Any]) -> Any:
#         """
#         Execute a skill action with given parameters.

#         Args:
#             action: The action name (e.g., "search", "add", "list")
#             params: Parameters for the action

#         Returns:
#             Any JSON-serializable result
#         """
#         raise NotImplementedError(f"Skill '{self.name}' must implement execute()")

#     def get_schema(self) -> dict:
#         """Return skill metadata for the LLM prompt."""
#         return {
#             "name": self.name,
#             "description": self.description,
#             "actions": self.actions,
#         }


# class SkillRegistry:
#     """
#     Central registry for all skill plugins.
#     Skills are auto-loaded from skills/ directory on startup.
#     """

#     SKILL_MODULES = [
#         "skills.web_search",
#         "skills.task_manager",
#         "skills.email_skill",
#         "skills.calendar_skill",
#     ]

#     def __init__(self):
#         self._skills: Dict[str, BaseSkill] = {}
#         self._load_all()

#     def _load_all(self):
#         """Auto-load all registered skill modules."""
#         for module_path in self.SKILL_MODULES:
#             try:
#                 module = importlib.import_module(module_path)
#                 skill_class = getattr(module, "Skill", None)
#                 if skill_class and issubclass(skill_class, BaseSkill):
#                     skill_instance = skill_class()
#                     self._skills[skill_instance.name] = skill_instance
#                     logger.info(f"✅ Loaded skill: {skill_instance.name}")
#                 else:
#                     logger.warning(f"Module {module_path} has no 'Skill' class")
#             except Exception as e:
#                 logger.error(f"Failed to load skill {module_path}: {e}")

#     def get(self, name: str) -> Optional[BaseSkill]:
#         """Get a skill by name."""
#         return self._skills.get(name)

#     def register(self, skill: BaseSkill):
#         """Manually register a skill (useful for testing/plugins)."""
#         self._skills[skill.name] = skill
#         logger.info(f"Manually registered skill: {skill.name}")

#     def list_skills(self) -> List[dict]:
#         """List all registered skills with their schemas."""
#         return [s.get_schema() for s in self._skills.values()]



"""
skills/registry.py — Skill Plugin Registry
Auto-discovers and registers skill plugins from the skills/ directory.
"""

import importlib
import logging
from typing import Any, Dict, List, Optional

logger = logging.getLogger("bharvishya.registry")


class BaseSkill:
    """
    Abstract base class for all Bharvishya skill plugins.

    Subclass this, define `name`, `description`, and implement `execute()`.
    """
    name: str = ""
    description: str = ""
    actions: List[str] = []

    async def execute(self, action: str, params: Dict[str, Any]) -> Any:
        """
        Execute a skill action with given parameters.

        Args:
            action: The action name (e.g., "search", "add", "list")
            params: Parameters for the action

        Returns:
            Any JSON-serializable result
        """
        raise NotImplementedError(f"Skill '{self.name}' must implement execute()")

    def get_schema(self) -> dict:
        """Return skill metadata for the LLM prompt."""
        return {
            "name": self.name,
            "description": self.description,
            "actions": self.actions,
        }


class SkillRegistry:
    """
    Central registry for all skill plugins.
    Skills are auto-loaded from skills/ directory on startup.
    """

    SKILL_MODULES = [
        "skills.web_search",
        "skills.task_manager",
        "skills.email_skill",
        "skills.calendar_skill",
    ]

    def __init__(self):
        self._skills: Dict[str, BaseSkill] = {}
        self._load_all()

    def _load_all(self):
        """Auto-load all registered skill modules."""
        for module_path in self.SKILL_MODULES:
            try:
                module = importlib.import_module(module_path)
                skill_class = getattr(module, "Skill", None)
                if skill_class and issubclass(skill_class, BaseSkill):
                    skill_instance = skill_class()
                    self._skills[skill_instance.name] = skill_instance
                    logger.info(f"✅ Loaded skill: {skill_instance.name}")
                else:
                    logger.warning(f"Module {module_path} has no 'Skill' class")
            except Exception as e:
                logger.error(f"Failed to load skill {module_path}: {e}")

    def get(self, name: str) -> Optional[BaseSkill]:
        """Get a skill by name."""
        return self._skills.get(name)

    def register(self, skill: BaseSkill):
        """Manually register a skill (useful for testing/plugins)."""
        self._skills[skill.name] = skill
        logger.info(f"Manually registered skill: {skill.name}")

    def list_skills(self) -> List[dict]:
        """List all registered skills with their schemas."""
        return [s.get_schema() for s in self._skills.values()]