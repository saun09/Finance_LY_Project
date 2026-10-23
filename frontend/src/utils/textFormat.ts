/** snake_case/kebab-case or any raw identifier -> Title Case words, for
 * displaying a backend value or free-text entry that might be stored in a
 * developer-friendly shape rather than a user-friendly one (e.g. a seeded
 * demo category "annual_vacation" -> "Annual Vacation"). Already-nice text
 * ("Rent") passes through unchanged apart from casing. Purely a display
 * transform -- never applied to a value before it's sent back to the API. */
export function titleCase(raw: string): string {
  return raw
    .replace(/[_-]+/g, ' ')
    .trim()
    .split(/\s+/)
    .filter(Boolean)
    .map((word) => word.charAt(0).toUpperCase() + word.slice(1).toLowerCase())
    .join(' ');
}
