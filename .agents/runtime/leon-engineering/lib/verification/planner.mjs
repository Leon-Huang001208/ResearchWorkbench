import {fail} from "./errors.mjs";
import {
  DEFAULT_POLICY_PATH,
  LEGACY_TIERS,
  LEVEL_ORDER,
  PLATFORM_ORDER,
  RISK_ORDER,
  SIGNALS,
  loadVerificationPolicy,
} from "./policy.mjs";
import {assertNoSymlinkComponents, normalizeRepositoryPath, safeProjectRoot} from "./path-safety.mjs";
import {assertCompleteChangedSet, discoverGitChangeSet} from "./changed-files.mjs";
import {createPlanBinding} from "./binding.mjs";

const CHANGE_KINDS = new Set([
  "documentation", "internal", "behavior", "contract", "schema", "database", "dependency", "ci", "security", "desktop",
]);
const KIND_MINIMUM = {
  documentation: "read-only",
  internal: "local-only",
  behavior: "isolated",
  contract: "full-delivery",
  schema: "full-delivery",
  database: "full-delivery",
  dependency: "full-delivery",
  ci: "full-delivery",
  security: "full-delivery",
  desktop: "full-delivery",
};

function unique(values) {
  return [...new Set(values)];
}

function legacyTierMax(...tiers) {
  return LEGACY_TIERS[Math.max(...tiers.map(tier => LEGACY_TIERS.indexOf(tier)))];
}

function legacyMatches(file, prefix) {
  return prefix.endsWith("/") ? file.startsWith(prefix) : file === prefix;
}

function verifierClosure(ids, verifiers, changedFiles, reasons) {
  return unique(ids).sort().map(id => {
    const verifier = verifiers[id];
    const appended = verifier.appendChangedFiles
      ? changedFiles.filter(file => verifier.extensions.length === 0 || verifier.extensions.some(extension => file.endsWith(extension)))
      : [];
    return {
      id,
      kind: verifier.kind,
      argv: [...verifier.argv, ...appended],
      cwd: verifier.cwd,
      reason: unique(reasons.get(id) ?? []),
    };
  });
}

export function buildLegacyVerificationPlan({projectRoot, riskTier, changeKind, changedFiles}) {
  if (!LEGACY_TIERS.includes(riskTier)) fail("ARGUMENT_ERROR", "invalid risk tier");
  if (!CHANGE_KINDS.has(changeKind)) fail("ARGUMENT_ERROR", "invalid change kind");
  if (!Array.isArray(changedFiles) || changedFiles.length === 0) fail("ARGUMENT_ERROR", "at least one changed file is required");
  const root = safeProjectRoot(projectRoot);
  const files = unique(changedFiles.map(file => normalizeRepositoryPath(file))).sort();
  const policy = loadVerificationPolicy({projectRoot: root});
  if (policy.schemaVersion !== 1) fail("POLICY_ERROR", "legacy planner requires policy schema 1");
  const matchedByFile = new Map(files.map(file => [
    file,
    policy.rules.filter(rule => rule.prefixes.some(prefix => legacyMatches(file, prefix))),
  ]));
  const unmappedPaths = files.filter(file => matchedByFile.get(file).length === 0);
  const matched = unique([...matchedByFile.values()].flat());
  let effectiveRiskTier = legacyTierMax(riskTier, KIND_MINIMUM[changeKind], ...matched.map(rule => rule.minimumTier));
  const escalationReason = [];
  if (LEGACY_TIERS.indexOf(KIND_MINIMUM[changeKind]) > LEGACY_TIERS.indexOf(riskTier)) {
    escalationReason.push(`change-kind:${changeKind}`);
  }
  for (const rule of matched) {
    if (LEGACY_TIERS.indexOf(rule.minimumTier) > LEGACY_TIERS.indexOf(riskTier)) escalationReason.push(`rule:${rule.name}`);
  }
  if (unmappedPaths.length > 0) {
    effectiveRiskTier = "full-delivery";
    escalationReason.push("unmapped-paths");
  }
  const reasons = new Map();
  for (const rule of matched) {
    for (const id of [...rule.tests, ...rule.lints]) {
      reasons.set(id, [...(reasons.get(id) ?? []), rule.name]);
    }
  }
  return {
    schemaVersion: 1,
    projectRoot: root,
    requestedRiskTier: riskTier,
    effectiveRiskTier,
    changeKind,
    changedFiles: files,
    requiredGates: unique([
      ...matched.flatMap(rule => rule.gates),
      ...(effectiveRiskTier === "full-delivery" ? ["delivery-receipt"] : []),
    ]).sort(),
    testClosure: verifierClosure(matched.flatMap(rule => rule.tests), policy.verifiers, files, reasons),
    lintClosure: verifierClosure(matched.flatMap(rule => rule.lints), policy.verifiers, files, reasons),
    documentationClosure: unique(matched.flatMap(rule => rule.documentation)).sort(),
    ciClosure: unique(matched.flatMap(rule => rule.ci)).sort(),
    unmappedPaths,
    escalationReason: unique(escalationReason).sort(),
  };
}

function matches(match, changedFile) {
  if (match.excludePrefixes.some(prefix => changedFile.startsWith(prefix))) return false;
  const segments = changedFile.split("/");
  return match.files.includes(changedFile) ||
    match.prefixes.some(prefix => changedFile.startsWith(prefix)) ||
    match.segments.some(segment => segments.includes(segment)) ||
    match.suffixes.some(suffix => changedFile.endsWith(suffix));
}

function ownsDelegatedPrefix(match, prefix) {
  return match.files.some(file => file.startsWith(prefix)) || match.prefixes.some(candidate => candidate.startsWith(prefix));
}

function appendUnique(target, seen, values) {
  for (const value of values) {
    if (seen.has(value)) continue;
    seen.add(value);
    target.push(value);
  }
}

function selectedCatalogItems(policy, category, ids, maximumLevelIndex) {
  const items = [];
  for (const id of ids) {
    const entry = policy.catalogs[category].get(id);
    if (LEVEL_ORDER.indexOf(entry.level) > maximumLevelIndex) continue;
    items.push(policy.schemaVersion === 3 ? {
      id,
      level: entry.level,
      lane: entry.lane,
      gate: entry.gate,
      platforms: [...entry.platforms],
      category,
      value: entry.value,
    } : {
      id,
      level: entry.level,
      execution: entry.execution,
      category,
      value: entry.value,
    });
  }
  return items;
}

function nextLevel(level) {
  return LEVEL_ORDER[Math.min(LEVEL_ORDER.indexOf(level) + 1, LEVEL_ORDER.length - 1)];
}

function orderedPlatformUnion(values) {
  const selected = new Set(values.flat());
  return PLATFORM_ORDER.filter(platform => selected.has(platform));
}

export function planVerification({projectRoot, changedFiles, signals = []}) {
  const root = safeProjectRoot(projectRoot);
  if (!Array.isArray(changedFiles) || changedFiles.length === 0) fail("ARGUMENT_ERROR", "at least one changed file is required");
  const normalizedFiles = [];
  const seenFiles = new Set();
  for (const changedFile of changedFiles) {
    const normalized = normalizeRepositoryPath(changedFile);
    assertNoSymlinkComponents(root, normalized, {required: false, code: "PATH_ERROR"});
    if (!seenFiles.has(normalized)) {
      seenFiles.add(normalized);
      normalizedFiles.push(normalized);
    }
  }
  const normalizedSignals = [];
  for (const signal of signals) {
    if (!SIGNALS.has(signal)) fail("ARGUMENT_ERROR", "unsupported escalation signal");
    if (!normalizedSignals.includes(signal)) normalizedSignals.push(signal);
  }
  const policy = loadVerificationPolicy({projectRoot: root});
  if (policy.schemaVersion === 1) fail("POLICY_ERROR", "shared planner requires policy schema 2 or 3");

  let riskIndex = 0;
  let levelIndex = 0;
  const reasons = [];
  const reasonKeys = new Set();
  const impact = [];
  const impactKeys = new Set();
  const ruleIds = [];
  const ruleSeen = new Set();
  const impactIds = [];
  const impactSeen = new Set();
  const highCouplingImpactIds = new Set();
  const gateIds = {tests: [], documentation: [], ci: [], ...(policy.schemaVersion === 3 ? {realMachine: []} : {})};
  const gateSeen = Object.fromEntries(Object.keys(gateIds).map(category => [category, new Set()]));
  const selectedPlatforms = [];
  const uncoveredRisks = [];

  for (const changedFile of normalizedFiles) {
    const delegatedPrefix = policy.delegatedPrefixes.find(prefix => changedFile.startsWith(prefix));
    const candidates = delegatedPrefix
      ? policy.rules.filter(rule => ownsDelegatedPrefix(rule.match, delegatedPrefix))
      : policy.rules;
    const matchedRules = candidates.filter(rule => matches(rule.match, changedFile));
    const selections = matchedRules.length > 0 ? matchedRules : [{id: "fallback", ...policy.fallback}];
    for (const selection of selections) {
      riskIndex = Math.max(riskIndex, RISK_ORDER.indexOf(selection.risk));
      levelIndex = Math.max(levelIndex, LEVEL_ORDER.indexOf(selection.minimumLevel));
      const reason = {path: changedFile, rule: selection.id, code: selection.reason};
      const reasonKey = JSON.stringify(reason);
      if (!reasonKeys.has(reasonKey)) {
        reasonKeys.add(reasonKey);
        reasons.push(reason);
      }
      const impactRecord = {
        path: changedFile,
        rule: selection.id,
        reason: selection.reason,
        modules: [...selection.impact],
        coupling: selection.coupling,
        minimumLevel: selection.minimumLevel,
      };
      const impactKey = JSON.stringify(impactRecord);
      if (!impactKeys.has(impactKey)) {
        impactKeys.add(impactKey);
        impact.push(impactRecord);
      }
      if (!ruleSeen.has(selection.id)) {
        ruleSeen.add(selection.id);
        ruleIds.push(selection.id);
      }
      for (const moduleId of selection.impact) {
        if (!impactSeen.has(moduleId)) {
          impactSeen.add(moduleId);
          impactIds.push(moduleId);
        }
        if (selection.coupling === "high") highCouplingImpactIds.add(moduleId);
      }
      for (const category of Object.keys(gateIds)) {
        appendUnique(gateIds[category], gateSeen[category], selection[category]);
      }
      if (policy.schemaVersion === 3) selectedPlatforms.push(selection.platforms);
      if (selection.id === "fallback" && !uncoveredRisks.includes("unknown_impact_boundary")) {
        uncoveredRisks.push("unknown_impact_boundary");
      }
    }
  }

  const escalations = [];
  if (highCouplingImpactIds.size >= policy.escalation.highCouplingImpactThreshold) {
    const targetIndex = LEVEL_ORDER.indexOf(policy.escalation.targetLevel);
    if (targetIndex > levelIndex) {
      const fromLevel = LEVEL_ORDER[levelIndex];
      levelIndex = targetIndex;
      escalations.push({
        code: "multiple_high_coupling_modules",
        fromLevel,
        toLevel: LEVEL_ORDER[levelIndex],
        impacts: [...highCouplingImpactIds],
      });
    }
  }
  for (const signal of normalizedSignals) {
    const fromLevel = LEVEL_ORDER[levelIndex];
    const toLevel = nextLevel(fromLevel);
    levelIndex = LEVEL_ORDER.indexOf(toLevel);
    escalations.push({code: signal, fromLevel, toLevel, impacts: []});
  }

  const requiredLevel = LEVEL_ORDER[levelIndex];
  const tests = selectedCatalogItems(policy, "tests", gateIds.tests, levelIndex);
  const documentation = selectedCatalogItems(policy, "documentation", gateIds.documentation, levelIndex);
  const ci = selectedCatalogItems(policy, "ci", gateIds.ci, levelIndex);
  const realMachine = policy.schemaVersion === 3
    ? selectedCatalogItems(policy, "realMachine", gateIds.realMachine, levelIndex)
    : [];
  const selectedValidations = [...tests, ...documentation, ...ci, ...realMachine];
  if (selectedValidations.length === 0) fail("PLAN_ERROR", "insufficient verification closure");
  const validationsByLevel = Object.fromEntries(LEVEL_ORDER.map(level => [level, []]));
  for (const item of selectedValidations) validationsByLevel[item.level].push(item);

  const base = {
    schemaVersion: policy.schemaVersion,
    risk: RISK_ORDER[riskIndex],
    requiredLevel,
    ...(policy.schemaVersion === 3 ? {
      components: [...impactIds],
      platforms: orderedPlatformUnion([
        ...selectedPlatforms,
        ...selectedValidations.map(item => item.platforms),
      ]),
    } : {}),
    changeSummary: {fileCount: normalizedFiles.length, ruleIds, impactIds},
    changedFiles: normalizedFiles,
    impact,
    reasons,
    escalations,
    uncoveredRisks,
    validationsByLevel,
    tests,
    documentation,
    ci,
  };

  if (policy.schemaVersion === 2) {
    return {
      ...base,
      receiptTemplate: {
        plannedLevel: requiredLevel,
        changedFiles: normalizedFiles,
        requiredValidationIds: selectedValidations.filter(item => item.execution === "local").map(item => item.id),
        externalGateIds: selectedValidations.filter(item => item.execution === "external").map(item => item.id),
      },
    };
  }

  const local = selectedValidations.filter(item => item.lane === "local");
  return {
    ...base,
    local,
    realMachine,
    receiptTemplate: {
      plannedLevel: requiredLevel,
      changedFiles: normalizedFiles,
      requiredValidationIds: local.filter(item => item.gate === "merge").map(item => item.id),
      externalGateIds: ci.filter(item => item.gate === "merge").map(item => item.id),
      releaseGateIds: realMachine.filter(item => item.gate === "release").map(item => item.id),
    },
  };
}

export function planGitVerification({
  projectRoot,
  base,
  changedFiles,
  signals = [],
  policyPath = DEFAULT_POLICY_PATH,
}) {
  if (policyPath !== DEFAULT_POLICY_PATH) fail("ARGUMENT_ERROR", "custom policy paths are not supported by the canonical CLI");
  const root = safeProjectRoot(projectRoot);
  const discovered = discoverGitChangeSet({projectRoot: root, base});
  const completeFiles = assertCompleteChangedSet({discovered, explicitPaths: changedFiles});
  const plan = planVerification({projectRoot: root, changedFiles: completeFiles, signals});
  if (plan.schemaVersion !== 3) fail("POLICY_ERROR", "Git-bound planning requires policy schema 3");
  const changeSet = {entries: discovered.entries};
  const unbound = {...plan, changeSet};
  return {
    ...unbound,
    binding: createPlanBinding({projectRoot: root, policyPath, plan: unbound, changeSet: discovered}),
  };
}
