# -*- coding: utf-8 -*-
# This file is part of Quark-Engine - https://github.com/quark-engine/quark-engine
# See the file 'LICENSE' for copying permission.

import json
import os

import click
import numpy as np
from tqdm import tqdm

from quark import __version__, config
from quark.core.parallelquark import ParallelQuark
from quark.core.quark import Quark
from quark.core.struct.ruleobject import RuleObject
from quark.logo import logo
from quark.utils.colors import yellow
from quark.utils.graph import select_label_menu, show_comparison_graph
from quark.utils.pprint import print_info, print_success, print_warning
from quark.utils.weight import Weight

logo()


@click.version_option(version=__version__)
@click.command(no_args_is_help=True)
@click.option(
    "-s",
    "--summary",
    is_flag=False,
    flag_value="all_rules",
    help="Show summary report. Optionally specify the name of a rule/label",
)
@click.option(
    "-d",
    "--detail",
    is_flag=False,
    flag_value="all_rules",
    help="Show detail report. Optionally specify the name of a rule/label",
)
@click.option(
    "-o",
    "--output",
    help="Output report in JSON",
    type=click.Path(exists=False, file_okay=True, dir_okay=False),
    required=False,
)
@click.option(
    "-a",
    "--apk",
    help="APK file",
    type=click.Path(exists=True, file_okay=True, dir_okay=False),
    required=True,
    multiple=True,
)
@click.option(
    "-r",
    "--rule",
    help="Rules directory",
    type=click.Path(exists=True, file_okay=True, dir_okay=True),
    default=f"{config.HOME_DIR}quark-rules",
    required=False,
    show_default=True,
)
@click.option(
    "-g",
    "--graph",
    is_flag=True,
    help="Create call graph to call_graph_image directory",
    required=False,
)
@click.option(
    "-c",
    "--classification",
    is_flag=True,
    help="Show rules classification",
    required=False,
)
@click.option(
    "-t",
    "--threshold",
    help="Set the lower limit of the confidence threshold",
    type=click.Choice(["100", "80", "60", "40", "20"]),
    required=False,
)
@click.option(
    "-i",
    "--list",
    help="List classes, methods and descriptors",
    type=click.Choice(["all", "native", "custom"]),
    required=False,
)
@click.option(
    "-p",
    "--permission",
    help="List Android permissions",
    is_flag=True,
    required=False,
)
@click.option(
    "-l",
    "--label",
    help="Show report based on label of rules",
    type=click.Choice(["max", "detailed"]),
    required=False,
)
@click.option(
    "-C",
    "--comparison",
    help="Behaviors comparison based on max confidence of rule labels",
    required=False,
    is_flag=True,
)
@click.option(
    "--core-library",
    "core_library",
    help="Specify the core library used to analyze an APK",
    type=click.Choice(("androguard", "rizin"), case_sensitive=False),
    required=False,
    default="androguard",
)
@click.option(
    "--multi-process",
    "num_of_process",
    type=click.IntRange(min=1),
    help="Allow analyzing APK with N processes",
    required=False,
    default=1,
)
def entry_point(
    summary,
    detail,
    apk,
    rule,
    output,
    graph,
    classification,
    threshold,
    list,
    permission,
    label,
    comparison,
    core_library,
    num_of_process,
):
    """Quark is an Obfuscation-Neglect Android Malware Scoring System"""

    # Load rules
    rule_path_list = [
        os.path.join(rule, file)
        for file in os.listdir(rule)
        if file.endswith("json")
    ]

    if comparison:

        # selection of labels on which it will be done the comparison on radar chart
        # first look for all label found in the rule list
        all_labels = set()
        for rulepath in tqdm(rule_path_list):
            rule_checker = RuleObject(rulepath)
            labels = (
                rule_checker.label
            )  # array type, e.g. ['network', 'collection']
            for single_label in labels:
                all_labels.add(single_label)

        # let user choose a list of label on which it will be performed the analysis
        selected_label = np.array(
            select_label_menu(all_labels, min_labels=5, max_labels=15)
        )

        # perform label based analysis on the apk_
        malware_confidences = {}
        for apk_ in apk:
            data = (
                ParallelQuark(apk_, core_library, num_of_process)
                if num_of_process > 1
                else Quark(apk_, core_library)
            )
            all_labels = {}
            # dictionary containing
            # key: label
            # value: list of confidence values
            # $ print(all_rules["accessibility service"])
            # > [60, 40, 60, 40, 60, 40]

            rule_checker_list = [
                RuleObject(rulepath) for rulepath in rule_path_list
            ]

            # analyse malware only on rules where appears label selected
            rule_checker_list = [
                rule_checker
                for rule_checker in rule_checker_list
                if len(np.intersect1d(rule_checker.label, selected_label)) != 0
            ]

            if num_of_process > 1:
                data.apply_rules(rule_checker_list)

            for rule_checker in tqdm(rule_checker_list):
                # Run the checker
                data.run(rule_checker)
                confidence = rule_checker.check_item.count(True) * 20
                labels = (
                    rule_checker.label
                )  # array type, e.g. ['network', 'collection']
                for single_label in labels:
                    if single_label in all_labels:
                        all_labels[single_label].append(confidence)
                    else:
                        all_labels[single_label] = [confidence]

            # extrapolate data used to plot radar chart
            radar_data = {}
            for _label in selected_label:
                confidences = np.array(all_labels[_label])
                # on radar data use the maximum confidence for a certain label
                radar_data[_label] = np.max(confidences)

            radar_confidence = [
                value_ for _label, value_ in radar_data.items()
            ]
            malware_confidences[apk_.split("/")[-1]] = radar_confidence

        show_comparison_graph(
            title=f"Malicious Actions Comparison Between {len(apk)} Malwares",
            lables=selected_label,
            malware_confidences=malware_confidences,
            font_size=22,
        )

        return

    # Load APK
    data = (
        ParallelQuark(apk[0], core_library, num_of_process)
        if num_of_process > 1
        else Quark(apk[0], core_library)
    )

    if label:
        all_labels = {}
        # dictionary containing
        # key: label
        # value: list of confidence values
        # $ print(all_rules["accessibility service"])
        # > [60, 40, 60, 40, 60, 40]

        rule_checker_list = [
            RuleObject(rulepath) for rulepath in rule_path_list
        ]

        if num_of_process > 1:
            data.apply_rules(rule_checker_list)

        for rule_checker in tqdm(rule_checker_list):
            # Run the checker
            data.run(rule_checker)
            confidence = rule_checker.check_item.count(True) * 20
            labels = (
                rule_checker.label
            )  # array type, e.g. ['network', 'collection']
            for single_label in labels:
                if single_label in all_labels:
                    all_labels[single_label].append(confidence)
                else:
                    all_labels[single_label] = [confidence]

        # get how many label with max confidence >= 80%
        counter_high_confidence = sum(
            max(value) >= 80 for single_label, value in all_labels.items()
        )

        print_info(f"Total Label found: {yellow(len(all_labels))}")
        print_info(
            f"Rules with label which max confidence >= 80%: {yellow(counter_high_confidence)}"
        )

        data.show_label_report(rule, all_labels, label)
        print(data.quark_analysis.label_report_table)

    # Show summary report
    if summary:

        if summary == "all_rules":
            label_flag = False
        elif summary.endswith("json"):
            rule_path_list = [summary]
            label_flag = False
        else:
            label_flag = True

        rule_checker_list = [RuleObject(rule) for rule in rule_path_list]
        rule_checker_list = [
            rule_checker
            for rule_checker in rule_checker_list
            if (not label_flag) or (summary in rule_checker.label)
        ]

        if isinstance(data, ParallelQuark):
            data.apply_rules(rule_checker_list)

        for rule_checker in tqdm(rule_checker_list):
            # Run the checker
            data.run(rule_checker)

            data.show_summary_report(rule_checker, threshold)

        w = Weight(
            data.quark_analysis.score_sum, data.quark_analysis.weight_sum
        )
        print_warning(w.calculate())
        print_info(f"Total Score: {data.quark_analysis.score_sum}")
        print(data.quark_analysis.summary_report_table)

        if classification:
            data.show_rule_classification()
        if graph:
            data.show_call_graph()

    # Show detail report
    if detail:
        threshold_number = int(threshold) if threshold else 0

        if detail == "all_rules":
            label_flag = False
        elif detail.endswith("json"):
            rule_path_list = [detail]
            label_flag = False
        else:
            label_flag = True

        rule_checker_list = [RuleObject(rule) for rule in rule_path_list]
        rule_checker_list = [
            rule_checker
            for rule_checker in rule_checker_list
            if (not label_flag) or (detail in rule_checker.label)
        ]

        if isinstance(data, ParallelQuark):
            data.apply_rules(rule_checker_list)

        for rule_checker, rule_path in tqdm(
            zip(rule_checker_list, rule_path_list)
        ):
            # Run the checker
            data.run(rule_checker)

            confidence = rule_checker.check_item.count(True) * 20

            if confidence >= threshold_number:
                print(f"Rulepath: {rule_path}")
                print(f"Rule crime: {rule_checker.crime}")
                data.show_detail_report(rule_checker)
                print_success("OK")

        if classification:
            data.show_rule_classification()
        if graph:
            data.show_call_graph()

    # Show JSON report
    if output:

        rule_checker_list = [RuleObject(rule) for rule in rule_path_list]

        if isinstance(data, ParallelQuark):
            data.apply_rules(rule_checker_list)

        for rule_checker in tqdm(rule_checker_list):
            # Run the checker
            data.run(rule_checker)

            data.generate_json_report(rule_checker)

        json_report = data.get_json_report()

        with open(output, "w") as file:
            json.dump(json_report, file, indent=4)
            file.close()

    if list:

        if list == "all":
            for all_method in data.apkinfo.all_methods:
                print(all_method.full_name)
        if list == "native":
            for api in data.apkinfo.android_apis:
                print(api.full_name)
        if list == "custom":
            for custom_method in data.apkinfo.custom_methods:
                print(custom_method.full_name)

    if permission:

        for p in data.apkinfo.permissions:
            print(p)

    if isinstance(data, ParallelQuark):
        data.close()


if __name__ == "__main__":
    entry_point()
