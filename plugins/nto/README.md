# Node Tuning Operator Plugin (nto)

## Overview
The `nto` plugin automates creation of Tuned manifests (`tuned.openshift.io/v1`) for the OpenShift Node Tuning Operator. Use it when you need reproducible YAML that captures sysctl settings, tuned daemon sections, and recommendation rules without hand-writing multi-line manifests.

## Commands
- `/nto:generate-tuned-profile` – Generate a Tuned profile manifest from a natural language description of the desired parameters, sections, and targeting rules.

## Prerequisites
- Python 3.8 or newer must be available in the execution environment (the helper script is dependency-free beyond the standard library).
- Access to an OpenShift cluster if you plan to apply the generated manifest (`oc` CLI recommended for validation and application).

## Typical Workflow
1. Invoke `/nto:generate-tuned-profile` with a profile name, summary, and any sysctl, include, or section options.
2. Review the rendered YAML returned by the command or written to `.work/nto/<profile-name>/tuned.yaml` when using the helper script directly.
3. Validate the manifest with `oc apply --server-dry-run=client -f <path>` if desired.
4. Apply the manifest to the cluster or commit it to version control for automation.

## Related Files
- Command definition: `commands/generate-tuned-profile.md`
- Helper implementation: `skills/scripts/generate_tuned_profile.py`
