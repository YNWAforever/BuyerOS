/** Public build-time switch. Unset or any value other than `true` keeps the #35 shell. */
export function conversationHomeEnabled(value: string | undefined): boolean {
  return value === 'true';
}

export const illustrativeDiscussions = [
  {id: 'prepare-follow-up', title: 'Prepare follow-up', prompt: 'Help me prepare a thoughtful follow-up for buyers I have reviewed.', reply: 'Start with the offer facts and reviewed buyer context. A short follow-up can explain the fit, ask one clear question and leave the next step with the buyer.'},
  {id: 'review-buyers', title: 'Review buyers', prompt: 'What should I check before moving a buyer into follow-up?', reply: 'Review the company fit, source evidence and contact context in Buyers. Keep freeform notes separate from structured evidence, then prepare a draft for human review.'},
] as const;

const newDiscussion = {id: 'new', title: 'New discussion', prompt: '', reply: 'Choose an example discussion to explore the workspace. Conversations here are illustrative and are not saved.'} as const;
export type IllustrativeDiscussion = typeof illustrativeDiscussions[number] | typeof newDiscussion;

export function discussionForPath(pathname: string, enabled: boolean): IllustrativeDiscussion | undefined {
  if (!enabled) return undefined;
  if (pathname === '/app') return illustrativeDiscussions[0];
  if (pathname === '/app/discussions/new') return newDiscussion;
  return illustrativeDiscussions.find(item => pathname === `/app/discussions/${item.id}`);
}

export function isLiveOverviewRoute(pathname: string, enabled: boolean): boolean {
  return pathname === (enabled ? '/app/overview' : '/app');
}
