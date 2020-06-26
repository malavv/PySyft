from typing import List
import pythreepio
from pythreepio.threepio import Threepio
from pythreepio.command import Command
from syft.execution.computation import ComputationAction
from syft.execution.role import Role
from syft.execution.placeholder import PlaceHolder
from syft.execution.translation import TranslationTarget
from syft.execution.translation.abstract import AbstractPlanTranslator


class PlanTranslatorThreepio(AbstractPlanTranslator):
    """Parent translator class for all Threepio supported frameworks"""

    def __init__(self, plan):
        super().__init__(plan)

    def create_action(self, action, cmd):
        new_action = action.copy()
        new_action.name = ".".join(cmd.attrs)
        new_action.args = tuple(cmd.args)
        new_action.kwargs = cmd.kwargs
        new_action.target = None
        return new_action

    def translate_multi_action(
        self, translated_cmds: List[Command], action: ComputationAction, role: Role
    ):
        cmd_config = translated_cmds.pop(0)
        store = {}
        actions = []
        for cmd in translated_cmds:
            # Create local store of placeholders
            if cmd.placeholder_output is not None:
                store[cmd.placeholder_output] = PlaceHolder(role=self.plan.role)

            for i, arg in enumerate(cmd.args):
                if type(arg) == pythreepio.command.Placeholder:
                    # Replace any threepio placeholders w/ pysyft placeholders
                    cmd.args[i] = store.get(arg.key, None)

            # Create action informat needed for role's register_action method
            role_action = (
                (".".join(cmd.attrs), None, tuple(cmd.args), cmd.kwargs),
                store[cmd.placeholder_output],
            )
            role.register_action(role_action, ComputationAction)

    def translate_action(
        self, action: ComputationAction, to_framework: str, role: Role
    ) -> ComputationAction:
        """Uses threepio to perform command level translation given a specific action"""
        threepio = Threepio(self.plan.base_framework, to_framework, None)
        function_name = action.name.split(".")[-1]
        args = action.args if action.target is None else (action.target, *action.args)
        translated_cmds = threepio.translate(Command(function_name, args, action.kwargs))

        if len(translated_cmds) > 1:
            return self.translate_multi_action(translated_cmds, action, role)

        for cmd in translated_cmds:
            role_action = (
                (".".join(cmd.attrs), None, tuple(cmd.args), cmd.kwargs),
                PlaceHolder(id=action.return_ids[0]),
            )
            role.register_action(role_action, ComputationAction)

    def translate_framework(self, to_framework: str) -> Role:
        """Translates current plan's Role to specified framework"""
        plan = self.plan.copy()
        new_role = plan.role.copy()
        new_role.reset()
        # Check to see if plan has been translated to this framework yet
        if plan.roles.get(to_framework, None) is not None:
            plan.default_framework = to_framework
            return plan

        new_actions = []
        for action in plan.role.actions:
            self.translate_action(action, to_framework, new_role)
        return new_role


class PlanTranslatorTfjs(PlanTranslatorThreepio):
    """Performs translation from 'list of ops' Plan into 'list of ops in tfjs' Plan"""

    framework = TranslationTarget.TENSORFLOW_JS.value

    def __init__(self, plan):
        super().__init__(plan)

    def translate(self) -> Role:
        """Translate role of given plan to tensorflow.js"""
        return self.translate_framework(TranslationTarget.TENSORFLOW_JS.value)
