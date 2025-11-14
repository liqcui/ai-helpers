---
name: Generate Tuned Profile
description: Render tuned.openshift.io/v1 manifests using the helper script
---

# Generate Tuned Profile

Detailed instructions for running `generate_tuned_profile.py`, the helper script that backs `/nto:generate-tuned-profile`.

## When to Use This Skill
- You need to translate structured command inputs into a Tuned manifest file.
- You want to troubleshoot or iterate on the generated YAML outside of Claude by invoking the script directly.
- You must integrate the generator into automation (CI, GitOps pipelines, etc.).

## Prerequisites
- Python 3.8 or newer installed (`python3 --version`).
- Access to the repository checkout so the script path `plugins/nto/skills/scripts/generate_tuned_profile.py` is available.
- Optional: `oc` CLI if you plan to validate or apply the resulting manifest.

## Implementation Steps
### 1. Collect Inputs
- `--profile-name`: Tuned resource name.
- `--summary`: `[main]` section summary string.
- Repeatable options: `--include`, `--main-option`, `--variable`, `--sysctl`, `--section` (format `SECTION:KEY=VALUE`).
- Target selectors: `--machine-config-label key=value`, `--match-label key[=value]`.
- Optional: `--priority` (defaults to 20), `--namespace`, `--output`, `--dry-run`.

### 2. Run the Script
```bash
python3 plugins/nto/skills/scripts/generate_tuned_profile.py \
  --profile-name "$PROFILE" \
  --summary "$SUMMARY" \
  --sysctl net.core.netdev_max_backlog=16384 \
  --match-label tuned.openshift.io/custom-net \
  --output .work/nto/$PROFILE/tuned.yaml
```
- Omit `--output` to print to `<profile-name>.yaml` in the current directory.
- Add `--dry-run` to print the manifest to stdout.

### 3. Review Output
- Inspect the generated file to ensure all sections render as expected.
- Optionally format with `yq` or open in an editor for readability.

### 4. Validate and Apply
- Dry-run apply: `oc apply --server-dry-run=client -f <manifest>`.
- Apply for real: `oc apply -f <manifest>`.

## Error Handling
- Missing required options raise `ValueError` and print `error: <message>` to stderr.
- Ensure at least one `--machine-config-label` or `--match-label` is provided; otherwise the script exits non-zero.
- Invalid `KEY=VALUE` or `SECTION:KEY=VALUE` inputs produce descriptive errors. Fix the offending argument and rerun.

## Examples
```bash
python3 plugins/nto/skills/scripts/generate_tuned_profile.py \
  --profile-name realtime-worker \
  --summary "Realtime tuned profile" \
  --include openshift-node --include realtime \
  --variable isolated_cores=1 \
  --section bootloader:cmdline_ocp_realtime=+systemd.cpu_affinity=${not_isolated_cores_expanded} \
  --machine-config-label machineconfiguration.openshift.io/role=worker-rt \
  --priority 25 \
  --output .work/nto/realtime-worker/tuned.yaml
```
