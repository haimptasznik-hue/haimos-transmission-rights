#!/usr/bin/env node

const fs = require('fs');
const os = require('os');
const path = require('path');
const crypto = require('crypto');

const mode = (process.argv[2] || 'full').toLowerCase();
const workspaceRoot = path.resolve(__dirname, '..', '..');

const distBundlePath = path.join(workspaceRoot, 'dist', 'mac-arm64', 'HaimOS.app');
const desktopBundlePath = path.join(os.homedir(), 'Desktop', 'HaimOS.app');
const canonicalBundlePath = path.join('/Applications', 'HaimOS.app');

const codePaths = [
  'main.js',
  'preload.js',
  'app.py',
  'nna_map_module.py',
  'renderer',
  'backend',
  'eye',
  path.join('scripts', 'projects'),
];

const ignoredNames = new Set(['.DS_Store', '__pycache__']);

function exists(targetPath) {
  try {
    fs.accessSync(targetPath, fs.constants.F_OK);
    return true;
  } catch {
    return false;
  }
}

function getBundleResourceApp(bundlePath) {
  return path.join(bundlePath, 'Contents', 'Resources', 'app');
}

function ensureDir(targetPath) {
  fs.mkdirSync(targetPath, { recursive: true });
}

function removePath(targetPath) {
  if (!exists(targetPath)) {
    return;
  }
  fs.rmSync(targetPath, { recursive: true, force: true });
}

function copyCodePathToBundle(relativeCodePath, bundleResourceApp) {
  const sourcePath = path.join(workspaceRoot, relativeCodePath);
  const targetPath = path.join(bundleResourceApp, relativeCodePath);

  if (!exists(sourcePath)) {
    return { copied: false, skipped: true, reason: 'source-missing', relativeCodePath };
  }

  ensureDir(path.dirname(targetPath));
  fs.cpSync(sourcePath, targetPath, { recursive: true, force: true });
  return { copied: true, skipped: false, relativeCodePath };
}

function collectRelativeFilesFromPath(relativePath) {
  const sourcePath = path.join(workspaceRoot, relativePath);
  if (!exists(sourcePath)) {
    return [];
  }

  const stat = fs.statSync(sourcePath);
  if (stat.isFile()) {
    return [relativePath];
  }

  const files = [];

  function walk(currentAbsPath, currentRelPath) {
    const entries = fs.readdirSync(currentAbsPath, { withFileTypes: true });
    for (const entry of entries) {
      if (ignoredNames.has(entry.name) || entry.name.endsWith('.pyc')) {
        continue;
      }

      const childAbsPath = path.join(currentAbsPath, entry.name);
      const childRelPath = path.join(currentRelPath, entry.name);

      if (entry.isDirectory()) {
        walk(childAbsPath, childRelPath);
      } else if (entry.isFile()) {
        files.push(childRelPath);
      }
    }
  }

  walk(sourcePath, relativePath);
  files.sort();
  return files;
}

function hashFile(filePath) {
  const buffer = fs.readFileSync(filePath);
  return crypto.createHash('sha256').update(buffer).digest('hex');
}

function ensureCanonicalBundleExists() {
  if (exists(canonicalBundlePath)) {
    return;
  }

  if (exists(distBundlePath)) {
    console.log(`Installing canonical app from dist: ${distBundlePath}`);
    fs.cpSync(distBundlePath, canonicalBundlePath, { recursive: true, force: true });
    return;
  }

  if (exists(desktopBundlePath) && !fs.lstatSync(desktopBundlePath).isSymbolicLink()) {
    console.log(`Moving Desktop app to canonical location: ${canonicalBundlePath}`);
    fs.renameSync(desktopBundlePath, canonicalBundlePath);
    return;
  }

  throw new Error('No canonical HaimOS.app found and no source bundle available to install. Run npm run build first.');
}

function syncCanonicalBundle() {
  ensureCanonicalBundleExists();

  const bundleResourceApp = getBundleResourceApp(canonicalBundlePath);
  if (!exists(bundleResourceApp)) {
    throw new Error(`Canonical bundle missing Resources/app: ${canonicalBundlePath}`);
  }

  console.log(`Syncing canonical bundle: ${canonicalBundlePath}`);
  for (const relativeCodePath of codePaths) {
    const result = copyCodePathToBundle(relativeCodePath, bundleResourceApp);
    if (result.copied) {
      console.log(`  ✓ ${relativeCodePath}`);
    }
  }
}

function enforceSingleInstall() {
  ensureCanonicalBundleExists();

  if (exists(desktopBundlePath)) {
    const stat = fs.lstatSync(desktopBundlePath);
    if (stat.isSymbolicLink()) {
      const currentTarget = fs.readlinkSync(desktopBundlePath);
      const resolvedCurrent = path.resolve(path.dirname(desktopBundlePath), currentTarget);
      if (resolvedCurrent !== canonicalBundlePath) {
        fs.unlinkSync(desktopBundlePath);
      }
    } else {
      console.log('Removing duplicate Desktop app bundle.');
      removePath(desktopBundlePath);
    }
  }

  if (!exists(desktopBundlePath)) {
    fs.symlinkSync(canonicalBundlePath, desktopBundlePath);
    console.log(`Created Desktop launcher symlink: ${desktopBundlePath} -> ${canonicalBundlePath}`);
  }
}

function verifySingleInstall() {
  let mismatches = 0;

  if (!exists(canonicalBundlePath)) {
    console.warn(`Canonical app missing: ${canonicalBundlePath}`);
    mismatches += 1;
  }

  if (!exists(desktopBundlePath)) {
    console.warn(`Desktop launcher missing: ${desktopBundlePath}`);
    mismatches += 1;
  } else {
    const desktopStat = fs.lstatSync(desktopBundlePath);
    if (!desktopStat.isSymbolicLink()) {
      console.warn('Desktop HaimOS.app must be a symlink to canonical app, but is a standalone bundle.');
      mismatches += 1;
    } else {
      const resolvedTarget = path.resolve(path.dirname(desktopBundlePath), fs.readlinkSync(desktopBundlePath));
      if (resolvedTarget !== canonicalBundlePath) {
        console.warn(`Desktop symlink target mismatch: ${resolvedTarget}`);
        mismatches += 1;
      }
    }
  }

  const canonicalResources = getBundleResourceApp(canonicalBundlePath);
  if (!exists(canonicalResources)) {
    console.warn(`Canonical bundle missing Resources/app: ${canonicalBundlePath}`);
    mismatches += 1;
  } else {
    const sourceFiles = codePaths.flatMap(collectRelativeFilesFromPath).sort();
    const drift = [];

    for (const relativeFile of sourceFiles) {
      const sourceFile = path.join(workspaceRoot, relativeFile);
      const targetFile = path.join(canonicalResources, relativeFile);

      if (!exists(targetFile)) {
        drift.push(`${relativeFile} (missing)`);
        continue;
      }

      if (hashFile(sourceFile) !== hashFile(targetFile)) {
        drift.push(`${relativeFile} (hash mismatch)`);
      }
    }

    if (drift.length > 0) {
      mismatches += drift.length;
      console.warn(`Canonical app drift detected (${drift.length} files):`);
      for (const mismatch of drift.slice(0, 15)) {
        console.warn(`  - ${mismatch}`);
      }
      if (drift.length > 15) {
        console.warn(`  - ... and ${drift.length - 15} more`);
      }
    } else {
      console.log('Canonical app verification: OK');
    }
  }

  return { ok: mismatches === 0, mismatches };
}

function printUsage() {
  console.log('Usage: node scripts/ops/sync-installed-apps.js [sync|verify|enforce-single|full]');
}

if (!['sync', 'verify', 'enforce-single', 'full'].includes(mode)) {
  printUsage();
  process.exit(2);
}

try {
  if (mode === 'sync' || mode === 'full') {
    syncCanonicalBundle();
  }

  if (mode === 'enforce-single' || mode === 'full') {
    enforceSingleInstall();
  }

  if (mode === 'verify' || mode === 'full') {
    const verification = verifySingleInstall();
    if (!verification.ok) {
      console.error(`Verification failed: ${verification.mismatches} issue(s) found.`);
      process.exit(1);
    }
  }

  process.exit(0);
} catch (error) {
  console.error(error.message || String(error));
  process.exit(1);
}
