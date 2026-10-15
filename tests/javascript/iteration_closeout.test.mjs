import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import {execFileSync} from 'node:child_process';
import {verifiedFeatureRepair} from '../../scripts/git_safety.mjs';

function fixture(t) {
  const root = fs.realpathSync(fs.mkdtempSync(path.join(os.tmpdir(), 'iteration-repair-')));
  t.after(() => fs.rmSync(root, {recursive:true, force:true}));
  const git = (...args) => execFileSync('/usr/bin/git', ['-C', root, ...args], {encoding:'utf8'}).trim();
  git('init','-b','master'); git('config','user.name','Fixture'); git('config','user.email','fixture@example.invalid');
  fs.writeFileSync(path.join(root,'file'), 'base'); git('add','.'); git('commit','-m','base');
  const base = git('rev-parse','HEAD');
  git('switch','-c','codex/repair-check-feature'); fs.writeFileSync(path.join(root,'file'),'repair'); git('commit','-am','repair');
  const feature = git('rev-parse','HEAD');
  return {root,git,base,feature};
}

test('late feature tip is accepted only when its exact commits are in the candidate', t => {
  const {root,base,feature} = fixture(t);
  const receipt = {taskId:'repair-check',featureBranch:'codex/repair-check-feature',featureWorktree:root,featureCommit:base,integrationWorktree:root};
  assert.equal(verifiedFeatureRepair({projectRoot:root,receipt}), feature);
});

test('uncommitted repair cannot refresh the recorded feature identity', t => {
  const {root,base} = fixture(t);
  fs.writeFileSync(path.join(root,'file'),'uncommitted');
  assert.throws(() => verifiedFeatureRepair({projectRoot:root,receipt:{taskId:'repair-check',featureBranch:'codex/repair-check-feature',featureWorktree:root,featureCommit:base,integrationWorktree:root}}), {code:'FEATURE_REPAIR_UNVERIFIED'});
});

test('other branch ownership cannot be adopted as a repair', t => {
  const {root,base} = fixture(t);
  assert.throws(() => verifiedFeatureRepair({projectRoot:root,receipt:{taskId:'other-task',featureBranch:'codex/repair-check-feature',featureWorktree:root,featureCommit:base,integrationWorktree:root}}), {code:'FEATURE_REPAIR_UNVERIFIED'});
});
