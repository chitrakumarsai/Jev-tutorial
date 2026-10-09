import type { RecordingMeta } from '../../api/types';
import { formatDate } from '../../lib/format';

/** Says plainly that a replay shows recorded answers, from when and from which models. */
export function RecordingBadge({ recording }: { recording: RecordingMeta }) {
  return (
    <p className="run-badge">
      <span className="run-badge__kind">Recorded</span>{' '}
      <time dateTime={recording.recorded_at}>{formatDate(recording.recorded_at)}</time>
      {' · '}
      <code>{recording.jev_model}</code> vs <code>{recording.llm_model}</code>
    </p>
  );
}
