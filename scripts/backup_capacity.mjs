/** Single ordinary-file stream admission only. This is not a bound for pack,
 * checkout/apply, migration, APFS metadata, or other concurrent disk writers.
 */
import fs from 'node:fs';

const MAX_BYTES = (1n << 63n) - 1n;
export const STREAM_RESERVE = 2n * 1024n ** 3n;
// Explicit policy allowance for one new file in an existing private directory;
// it is not a measured upper bound for all filesystem metadata allocation.
export const STREAM_METADATA_ALLOWANCE = 1024n ** 2n;
const fail = code => {throw Object.assign(new Error(code), {code});};

function bytes(value, positive = false) {
  if (value === undefined || value === null) fail('BACKUP_CAPACITY_UNKNOWN');
  if (typeof value !== 'bigint' || value < (positive ? 1n : 0n) || value > MAX_BYTES) fail('BACKUP_CAPACITY_INVALID');
  return value;
}
function add(left, right) {
  if (left > MAX_BYTES - right) fail('BACKUP_CAPACITY_INVALID');
  return left + right;
}
export function fileStreamRequirement({fileBytes, blockSize} = {}) {
  const size = bytes(fileBytes), block = bytes(blockSize, true);
  const remainder = size % block;
  const rounded = remainder ? add(size, block - remainder) : size;
  return add(add(rounded, STREAM_METADATA_ALLOWANCE), STREAM_RESERVE);
}
export function measureAvailable(directory) {
  try {
    const stat = fs.statSync(directory, {bigint: true});
    if (!stat.isDirectory()) fail('BACKUP_CAPACITY_MEASUREMENT_FAILED');
    const space = fs.statfsSync(directory, {bigint: true});
    const blockSize = bytes(space.bsize, true), availableBlocks = bytes(space.bavail);
    if (availableBlocks > MAX_BYTES / blockSize) fail('BACKUP_CAPACITY_INVALID');
    return {device: bytes(stat.dev), blockSize, availableBytes: availableBlocks * blockSize};
  } catch (error) {
    if (error.code?.startsWith('BACKUP_CAPACITY_')) throw error;
    fail('BACKUP_CAPACITY_MEASUREMENT_FAILED');
  }
}

/** The caller pins/rechecks the destination directory and source file. The
 * optional dependencies are an internal test seam, never CLI input.
 */
export function admitFileStream({directory, fileBytes, measure = measureAvailable, onEvent = () => {}} = {}) {
  const event = {event: 'backup_capacity', phase: 'snapshot-stream', scope: 'single-file-content', metadataAllowanceBytes: String(STREAM_METADATA_ALLOWANCE), reserveBytes: String(STREAM_RESERVE)};
  let error;
  try {
    event.knownBytes = String(bytes(fileBytes));
    let actual;
    try {actual = measure(directory);} catch (failure) {
      if (failure.code?.startsWith('BACKUP_CAPACITY_')) throw failure;
      fail('BACKUP_CAPACITY_MEASUREMENT_FAILED');
    }
    const available = bytes(actual?.availableBytes), block = bytes(actual?.blockSize, true), device = bytes(actual?.device);
    const required = fileStreamRequirement({fileBytes, blockSize: block});
    Object.assign(event, {device: String(device), blockSize: String(block), availableBytes: String(available), requiredBytes: String(required)});
    if (available < required) fail('BACKUP_CAPACITY_INSUFFICIENT');
    event.status = 'PASS';
  } catch (failure) {
    error = failure;
    Object.assign(event, {status: 'FAIL', code: failure.code ?? 'BACKUP_CAPACITY_INVALID'});
  }
  try {onEvent(event);} catch {
    if (error) error.loggingCode = 'BACKUP_CAPACITY_LOG_FAILED';
    else fail('BACKUP_CAPACITY_LOG_FAILED');
  }
  if (error) throw error;
  return event;
}
