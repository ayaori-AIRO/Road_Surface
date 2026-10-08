// Local demonstration coordinates, not a surveyed road or a GPS fix.
export const origin = { latitude: 37.5665, longitude: 126.9780 };
export const route = [[0, 0], [450, 0], [450, 300], [0, 300], [0, 0]];
export const routeLength = 1500;
export function advanceDistance(distance, speedKmh, elapsedSeconds) {
  return distance + Math.max(0, speedKmh) / 3.6 * Math.max(0, elapsedSeconds);
}
export function positionAt(distance) {
  let remaining = ((distance % routeLength) + routeLength) % routeLength;
  for (let i = 1; i < route.length; i++) {
    const [ax, ay] = route[i - 1], [bx, by] = route[i];
    const length = Math.hypot(bx - ax, by - ay);
    if (remaining < length || i === route.length - 1) {
      const ratio = remaining / length;
      const x = ax + (bx - ax) * ratio, y = ay + (by - ay) * ratio;
      return { x, y,
        latitude: origin.latitude + y / 111320,
        longitude: origin.longitude + x / (111320 * Math.cos(origin.latitude * Math.PI / 180)),
        heading: (Math.atan2(bx - ax, by - ay) * 180 / Math.PI + 360) % 360,
      };
    }
    remaining -= length;
  }
}
