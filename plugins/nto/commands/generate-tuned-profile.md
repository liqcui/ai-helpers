---
description: Generate a Tuned (tuned.openshift.io/v1) profile manifest for the Node Tuning Operator
argument-hint: "[profile-name] [--summary ...] [--sysctl ...] [options]"
---

## Name
nto:generate-tuned-profile

## Synopsis
```
/nto:generate-tuned-profile [profile-name] [--summary TEXT] [--include VALUE ...] [--sysctl KEY=VALUE ...] [--match-label KEY[=VALUE] ...] [options]
```

## Description
The `nto:generate-tuned-profile` command streamlines creation of `tuned.openshift.io/v1` manifests for the OpenShift Node Tuning Operator. It captures the desired Tuned profile metadata, tuned daemon configuration blocks (e.g. `[sysctl]`, `[variables]`, `[bootloader]`), and recommendation rules, then invokes the helper script at `plugins/nto/skills/scripts/generate_tuned_profile.py` to render a ready-to-apply YAML file.

Use this command whenever you need to:
- Bootstrap a new Tuned custom profile targeting selected nodes or machine config pools
- Generate manifests that can be version-controlled alongside other automation
- Iterate on sysctl, bootloader, or service parameters without hand-editing multi-line YAML

The generated manifest follows the structure expected by the cluster Node Tuning Operator:
```
apiVersion: tuned.openshift.io/v1
kind: Tuned
metadata:
  name: <profile-name>
  namespace: openshift-cluster-node-tuning-operator
spec:
  profile:
  - data: |
      [main]
      summary=...
      include=...
      ...
    name: <profile-name>
  recommend:
  - machineConfigLabels: {...}
    match:
    - label: ...
      value: ...
    priority: <priority>
    profile: <profile-name>
```

## Implementation
1. **Collect inputs**
   - Confirm Python 3.8+ is available (`python3 --version`).
   - Gather the Tuned profile name, summary, optional include chain, sysctl values, variables, and any additional section lines (e.g. `[bootloader]`, `[service]`).
   - Determine targeting rules: either `--match-label` entries (node labels) or `--machine-config-label` entries (MachineConfigPool selectors).

2. **Build execution workspace**
   - Create or reuse `.work/nto/<profile-name>/`.
   - Decide on the manifest filename (default `tuned.yaml` inside the workspace) or provide `--output` to override.

3. **Invoke the generator script**
   - Run the helper with the collected switches:
     ```bash
     python3 plugins/nto/skills/scripts/generate_tuned_profile.py \
       --profile-name "$PROFILE_NAME" \
       --summary "$SUMMARY" \
       --include openshift-node \
       --sysctl net.core.netdev_max_backlog=16384 \
       --variable isolated_cores=1 \
       --section bootloader:cmdline_ocp_realtime=+systemd.cpu_affinity=${not_isolated_cores_expanded} \
       --machine-config-label machineconfiguration.openshift.io/role=worker-rt \
       --match-label tuned.openshift.io/elasticsearch="" \
       --priority 25 \
       --output ".work/nto/$PROFILE_NAME/tuned.yaml"
     ```
   - Use `--dry-run` to print the manifest to stdout before writing, if desired.

4. **Validate output**
   - Inspect the generated YAML (`yq e . .work/nto/$PROFILE_NAME/tuned.yaml` or open in an editor).
   - Optionally run `oc apply --server-dry-run=client -f .work/nto/$PROFILE_NAME/tuned.yaml` to confirm schema compatibility.

5. **Apply or distribute**
   - Apply to a cluster with `oc apply -f .work/nto/$PROFILE_NAME/tuned.yaml`.
   - Commit the manifest to Git or attach to automated pipelines as needed.

## Return Value
- **Success**: Path to the generated manifest and the profile name are returned to the caller.
- **Failure**: Script exits non-zero with stderr diagnostics (e.g. invalid `KEY=VALUE` pair, missing labels, unwritable output path).

## Examples

1. **Realtime worker profile targeting worker-rt MCP**
   ```
   /nto:generate-tuned-profile openshift-realtime \
     --summary "Custom realtime tuned profile" \
     --include openshift-node --include realtime \
     --variable isolated_cores=1 \
     --section bootloader:cmdline_ocp_realtime=+systemd.cpu_affinity=${not_isolated_cores_expanded} \
     --machine-config-label machineconfiguration.openshift.io/role=worker-rt \
     --output .work/nto/openshift-realtime/realtime.yaml
   ```

2. **Sysctl-only profile matched by node label**
   ```
   /nto:generate-tuned-profile custom-net-tuned \
     --summary "Increase conntrack table" \
     --sysctl net.netfilter.nf_conntrack_max=262144 \
     --match-label tuned.openshift.io/custom-net \
     --priority 18
   ```

3. **Preview manifest without writing to disk**
   ```
   /nto:generate-tuned-profile pidmax-test \
     --summary "Raise pid max" \
     --sysctl kernel.pid_max=131072 \
     --match-label tuned.openshift.io/pidmax="" \
     --dry-run
   ```

## Arguments:
- **$1** (`profile-name`): Name for the Tuned profile and manifest resource.
- **--summary**: Required summary string placed in the `[main]` section.
- **--include**: Optional include chain entries (multiple allowed).
- **--main-option**: Additional `[main]` section key/value pairs (`KEY=VALUE`).
- **--variable**: Add entries to the `[variables]` section (`KEY=VALUE`).
- **--sysctl**: Add sysctl settings to the `[sysctl]` section (`KEY=VALUE`).
- **--section**: Add lines to arbitrary sections using `SECTION:KEY=VALUE`.
- **--machine-config-label**: MachineConfigPool selector labels (`key=value`) applied under `machineConfigLabels`.
- **--match-label**: Node selector labels for the `recommend[].match[]` block; omit `=value` to match existence only.
- **--priority**: Recommendation priority (integer, default 20).
- **--namespace**: Override the manifest namespace (default `openshift-cluster-node-tuning-operator`).
- **--output**: Destination file path; defaults to `<profile-name>.yaml` in the current directory.
- **--dry-run**: Print manifest to stdout instead of writing to a file.

