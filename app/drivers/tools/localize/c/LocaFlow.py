import os
import re
from os.path import join

from app.drivers.tools.localize.AbstractLocalizeTool import AbstractLocalizeTool


class Valkyrie(AbstractLocalizeTool):
    def __init__(self):
        self.name = os.path.basename(__file__)[:-3].lower()
        super().__init__(self.name)
        self.image_name = "yuntongzhang/sec-fix-loc:latest"
        self.id = ""

    def populate_config_file(self, bug_info):
        self.dir_localization = join(self.dir_output, "localization")
        self.emit_normal("generating config file")
        config_path = join(self.dir_expr, f"{self.name}.config")
        conf_content = list()
        dir_src = f"{self.dir_expr}/src"
        conf_content.append(f"source_dir:{dir_src}\n")
        if bug_info.get(self.key_localization, None):
            localization = bug_info[self.key_localization]
            if len(localization) > 1:
                self.error_exit("Multiple localization not supported")
            else:
                conf_content.append(
                    f"source_file:{localization[0][self.key_fix_file]}\n"
                )
        conf_content.append(
            f"test_oracle:{self.dir_setup}/{bug_info[self.key_test_script]}\n"
        )
        conf_content.append(
            f"test_id_list:{','.join(bug_info[self.key_failing_test_identifiers])}\n"
        )
        build_script = bug_info[self.key_build_script]
        abs_path_b_script = f"{self.dir_setup}/{build_script}"
        if build_script:
            conf_content.append(f"build_script:{abs_path_b_script}\n")
        else:
            conf_content.append(f'build_script:-c "exit 0"\n')
        conf_content.append(f"output_dir:{self.dir_output}\n")
        self.write_file(conf_content, config_path)
        return config_path

    def run_localization(self, bug_info, localization_config_info):
        conf_path = self.populate_config_file(bug_info)
        super(Valkyrie, self).run_localization(bug_info, localization_config_info)
        task_conf_id = str(self.current_task_profile_id.get("NA"))
        bug_id = str(bug_info[self.key_bug_id])
        self.id = bug_id
        timeout = str(localization_config_info[self.key_timeout])
        self.log_output_path = join(
            self.dir_logs,
            "{}-{}-{}-output.log".format(task_conf_id, self.name.lower(), bug_id),
        )

        timeout_m = str(float(timeout) * 60)
        additional_tool_param = localization_config_info[self.key_tool_params]
        self.timestamp_log_start()
        validate_command = (
            "bash -c 'stty cols 100 && stty rows 100 && timeout -k 5m {0}h valkyrie --conf=".format(
                timeout
            )
            + conf_path
            + " --only-validate "
            + additional_tool_param
            + "'"
        )

        status = self.run_command(validate_command, self.log_output_path)
        self.process_status(status)

        self.timestamp_log_end()
        self.emit_highlight("log file: {0}".format(self.log_output_path))

    def analyse_output(self, dir_info, bug_id, fail_list):
        self.emit_normal("reading output")
        dir_results = join(self.dir_expr, "result")
        task_conf_id = str(self.current_task_profile_id.get("NA"))
        self.log_stats_path = join(
            self.dir_logs,
            "{}-{}-{}-stats.log".format(task_conf_id, self.name.lower(), bug_id),
        )
        regex = re.compile("(.*-output.log$)")
        for _, _, files in os.walk(dir_results):
            for file in files:
                if regex.match(file) and self.name in file:
                    self.log_output_path = dir_results + "/" + file
                    break
        if not self.log_output_path or not self.is_file(self.log_output_path):
            self.emit_warning("no output log file found")
            return self.stats

        self.emit_highlight(" Log File: " + self.log_output_path)
        is_timeout = True
        if self.is_file(self.log_output_path):
            log_lines = self.read_file(self.log_output_path, encoding="iso-8859-1")
            for line in log_lines:
                if "Runtime Error" in line:
                    self.stats.error_stats.is_error = True
                elif "statistics" in line:
                    is_timeout = False

        if self.stats.error_stats.is_error:
            self.emit_error("[error] error detected in logs")
        if is_timeout:
            self.emit_warning("[warning] timeout before ending")
        return self.stats
