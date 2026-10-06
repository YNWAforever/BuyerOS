/** Convert browser UTF-16 offsets without changing the cited source text. */
export function selectionToCodePoints(text: string, startUTF16: number, endUTF16: number): { start: number; end: number } {
  if (typeof text !== 'string' || !Number.isInteger(startUTF16) || !Number.isInteger(endUTF16)
      || startUTF16 < 0 || endUTF16 < startUTF16 || endUTF16 > text.length) {
    throw new RangeError('Selection must be an exact UTF-16 range in the source');
  }
  const boundaries = new Map<number, number>([[0, 0]]);
  let point = 0;
  for (let unit = 0; unit < text.length;) {
    const first = text.charCodeAt(unit);
    if (first >= 0xd800 && first <= 0xdbff) {
      const second = text.charCodeAt(unit + 1);
      if (!(second >= 0xdc00 && second <= 0xdfff)) throw new RangeError('Malformed source surrogate');
      unit += 2;
    } else {
      if (first >= 0xdc00 && first <= 0xdfff) throw new RangeError('Malformed source surrogate');
      unit += 1;
    }
    boundaries.set(unit, ++point);
  }
  const start = boundaries.get(startUTF16), end = boundaries.get(endUTF16);
  if (start === undefined || end === undefined) throw new RangeError('Selection splits a surrogate pair');
  return { start, end };
}
