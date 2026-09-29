export class VerificationError extends Error {
  constructor(code, message) {
    super(message);
    this.code = code;
  }
}

export function fail(code, message) {
  throw new VerificationError(code, message);
}
