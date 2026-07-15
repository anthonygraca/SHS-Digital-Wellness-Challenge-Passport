import { useCallback, useEffect, useRef, useState } from "react";
import { QRCodeSVG } from "qrcode.react";
import { useSession } from "../../../auth/SessionProvider";
import * as api from "../../../api/challenges";
import * as themeApi from "../../../api/themes";
import type {
  AssessmentItem,
  Challenge,
  ChallengeSummary,
  CheckIn,
  CheckInAudit,
  Task,
} from "../../../types/challenge";
import type { Theme } from "../../../types/theme";
import styles from "./ChallengeBuilder.module.css";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

type View = { kind: "list" } | { kind: "detail"; id: number };

// ---------------------------------------------------------------------------
// Tiny helpers
// ---------------------------------------------------------------------------

function StatusBadge({ status }: { status: string }) {
  const cls = status === "published" ? styles.statusPublished : styles.statusDraft;
  return <span className={`${styles.statusBadge} ${cls}`}>{status}</span>;
}

function fmtDate(d: string | null | undefined) {
  if (!d) return "—";
  const [y, m, day] = d.split("-");
  return `${m}/${day}/${y}`;
}

// ---------------------------------------------------------------------------
// Challenge list view
// ---------------------------------------------------------------------------

function ChallengeList({
  onOpen,
  onCreated,
}: {
  onOpen: (id: number) => void;
  onCreated: (id: number) => void;
}) {
  const [challenges, setChallenges] = useState<ChallengeSummary[]>([]);
  const [loading, setLoading] = useState(true);
  const [showForm, setShowForm] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      setChallenges(await api.listChallenges());
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { void load(); }, [load]);

  return (
    <>
      <div className={styles.listHeader}>
        <h2>Challenges</h2>
        <button
          type="button"
          className={styles.btnPrimary}
          onClick={() => setShowForm(true)}
        >
          + New challenge
        </button>
      </div>

      {loading && <p className={styles.empty}>Loading…</p>}

      {!loading && challenges.length === 0 && (
        <p className={styles.empty}>No challenges yet — create the first one.</p>
      )}

      {challenges.map((c) => (
        <div
          key={c.id}
          role="button"
          tabIndex={0}
          className={styles.challengeCard}
          onClick={() => onOpen(c.id)}
          onKeyDown={(e) => e.key === "Enter" && onOpen(c.id)}
          aria-label={`Open ${c.name}`}
        >
          <div className={styles.challengeCardInfo}>
            <h3>{c.name}</h3>
            <p>
              {c.semester} · {fmtDate(c.start_date)} – {fmtDate(c.end_date)}
            </p>
          </div>
          <StatusBadge status={c.status} />
        </div>
      ))}

      {showForm && (
        <ChallengeFormModal
          onClose={() => setShowForm(false)}
          onSaved={(c) => { setShowForm(false); onCreated(c.id); }}
        />
      )}
    </>
  );
}

// ---------------------------------------------------------------------------
// Challenge detail view
// ---------------------------------------------------------------------------

function ChallengeDetail({
  id,
  onBack,
}: {
  id: number;
  onBack: () => void;
}) {
  const [challenge, setChallenge] = useState<Challenge | null>(null);
  const [loading, setLoading] = useState(true);
  const [editChallenge, setEditChallenge] = useState(false);
  const [addingTask, setAddingTask] = useState(false);
  const [editingTask, setEditingTask] = useState<Task | null>(null);
  const [itemsTask, setItemsTask] = useState<Task | null>(null);
  const [checkinsTask, setCheckinsTask] = useState<Task | null>(null);
  const [editingTheme, setEditingTheme] = useState(false);
  const [themes, setThemes] = useState<Theme[]>([]);
  const [publishing, setPublishing] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      setChallenge(await api.getChallenge(id));
    } finally {
      setLoading(false);
    }
  }, [id]);

  useEffect(() => { void load(); }, [load]);

  // Only for naming the applied theme; a failed lookup falls back to its id.
  const refreshThemes = useCallback(
    () => themeApi.listThemes().then(setThemes).catch(() => setThemes([])),
    [],
  );

  useEffect(() => { void refreshThemes(); }, [refreshThemes]);

  const themeName =
    themes.find((t) => t.id === challenge?.theme_id)?.name ?? challenge?.theme_id;

  async function handlePublish() {
    if (!challenge) return;
    setPublishing(true);
    setError(null);
    try {
      const updated = await api.publishChallenge(challenge.id);
      setChallenge(updated);
    } catch (e) {
      setError(e instanceof api.ApiError ? e.message : "Publish failed");
    } finally {
      setPublishing(false);
    }
  }

  async function handleDeleteTask(taskId: number) {
    if (!challenge) return;
    await api.deleteTask(challenge.id, taskId);
    await load();
  }

  async function handleReorder(newOrder: number[]) {
    if (!challenge) return;
    const updated = await api.reorderTasks(challenge.id, { task_ids: newOrder });
    setChallenge((prev) => prev ? { ...prev, tasks: updated } : prev);
  }

  if (loading) return <p className={styles.empty}>Loading…</p>;
  if (!challenge) return <p className={styles.empty}>Challenge not found.</p>;

  return (
    <>
      <div className={styles.detailHeader}>
        <button type="button" className={styles.backBtn} onClick={onBack}>
          ← All challenges
        </button>
        <div className={styles.detailMeta}>
          <h2>{challenge.name}</h2>
          <div className={styles.metaRow}>
            <span>{challenge.semester}</span>
            <span>{fmtDate(challenge.start_date)} – {fmtDate(challenge.end_date)}</span>
            <StatusBadge status={challenge.status} />
            <span className={styles.themeBadge}>
              Theme: {challenge.theme_id ? themeName : "Default"}
            </span>
          </div>
          {error && <p className={styles.error}>{error}</p>}
          <div className={styles.detailActions}>
            <button
              type="button"
              className={styles.btnSecondary}
              onClick={() => setEditChallenge(true)}
            >
              Edit details
            </button>
            {challenge.theme_id && (
              <button
                type="button"
                className={styles.btnSecondary}
                onClick={() => setEditingTheme(true)}
              >
                Edit theme
              </button>
            )}
            {challenge.status === "draft" && (
              <button
                type="button"
                className={styles.btnPrimary}
                onClick={() => void handlePublish()}
                disabled={publishing}
              >
                {publishing ? "Publishing…" : "Publish"}
              </button>
            )}
          </div>
        </div>
      </div>

      <div className={styles.taskSection}>
        <h3>Weekly tasks ({challenge.tasks.length})</h3>

        <TaskList
          tasks={challenge.tasks}
          onEdit={setEditingTask}
          onDelete={(taskId) => void handleDeleteTask(taskId)}
          onReorder={handleReorder}
          onManageItems={setItemsTask}
          onManageCheckins={setCheckinsTask}
        />

        <button
          type="button"
          className={styles.btnSecondary}
          style={{ marginTop: 12 }}
          onClick={() => setAddingTask(true)}
        >
          + Add task
        </button>
      </div>

      {editChallenge && (
        <ChallengeFormModal
          existing={challenge}
          onClose={() => setEditChallenge(false)}
          onSaved={(c) => { setEditChallenge(false); setChallenge(c); }}
        />
      )}

      {addingTask && (
        <TaskFormModal
          challengeId={challenge.id}
          onClose={() => setAddingTask(false)}
          onSaved={() => { setAddingTask(false); void load(); }}
        />
      )}

      {editingTask && (
        <TaskFormModal
          challengeId={challenge.id}
          existing={editingTask}
          onClose={() => setEditingTask(null)}
          onSaved={() => { setEditingTask(null); void load(); }}
        />
      )}

      {itemsTask && (
        <AssessmentItemsPanel
          challengeId={challenge.id}
          task={itemsTask}
          onClose={() => { setItemsTask(null); void load(); }}
        />
      )}

      {checkinsTask && (
        <CompletionOverridePanel
          challengeId={challenge.id}
          task={checkinsTask}
          onClose={() => setCheckinsTask(null)}
        />
      )}

      {editingTheme && challenge.theme_id && (
        <ThemeEditorModal
          themeId={challenge.theme_id}
          onClose={() => setEditingTheme(false)}
          onSaved={() => { setEditingTheme(false); void refreshThemes(); }}
        />
      )}
    </>
  );
}

// ---------------------------------------------------------------------------
// Task list with HTML5 drag-to-reorder
// ---------------------------------------------------------------------------

function TaskList({
  tasks,
  onEdit,
  onDelete,
  onReorder,
  onManageItems,
  onManageCheckins,
}: {
  tasks: Task[];
  onEdit: (t: Task) => void;
  onDelete: (id: number) => void;
  onReorder: (ids: number[]) => Promise<void>;
  onManageItems: (t: Task) => void;
  onManageCheckins: (t: Task) => void;
}) {
  const dragSrc = useRef<number | null>(null); // index being dragged
  const [draggingIdx, setDraggingIdx] = useState<number | null>(null);
  const [overIdx, setOverIdx] = useState<number | null>(null);

  // Local optimistic order so the list snaps immediately before the server round-trip.
  const [localOrder, setLocalOrder] = useState<Task[]>(tasks);
  // Sync when parent refreshes
  useEffect(() => setLocalOrder(tasks), [tasks]);

  function handleDragStart(idx: number) {
    dragSrc.current = idx;
    setDraggingIdx(idx);
  }

  function handleDragEnter(idx: number) {
    if (dragSrc.current === null || dragSrc.current === idx) return;
    setOverIdx(idx);
  }

  function handleDragEnd() {
    const src = dragSrc.current;
    const dst = overIdx;
    dragSrc.current = null;
    setDraggingIdx(null);
    setOverIdx(null);
    if (src === null || dst === null || src === dst) return;

    const next = [...localOrder];
    const [moved] = next.splice(src, 1);
    next.splice(dst, 0, moved);
    setLocalOrder(next);
    void onReorder(next.map((t) => t.id));
  }

  if (localOrder.length === 0) {
    return (
      <p className={styles.empty} style={{ padding: "16px 0" }}>
        No tasks yet.
      </p>
    );
  }

  return (
    <ul className={styles.taskList} aria-label="Weekly tasks">
      {localOrder.map((task, idx) => (
        <li
          key={task.id}
          className={styles.taskItem}
          draggable
          data-dragging={draggingIdx === idx ? "true" : undefined}
          data-over={overIdx === idx ? "true" : undefined}
          onDragStart={() => handleDragStart(idx)}
          onDragEnter={() => handleDragEnter(idx)}
          onDragOver={(e) => e.preventDefault()}
          onDragEnd={handleDragEnd}
          aria-label={`Week ${task.position}: ${task.title}`}
        >
          <div className={styles.dragHandle} aria-hidden="true">
            <span /><span /><span />
          </div>

          <div className={styles.taskBody}>
            <p className={styles.taskTitle}>
              {task.position}. {task.title}
              {task.required && (
                <span className={styles.reqBadge} style={{ marginLeft: 8 }}>
                  Required
                </span>
              )}
            </p>
            <div className={styles.taskMeta}>
              {task.activity_type && <span>{task.activity_type}</span>}
              {task.location && <span>📍 {task.location}</span>}
              {(task.date_window_start || task.date_window_end) && (
                <span>
                  {fmtDate(task.date_window_start)} – {fmtDate(task.date_window_end)}
                </span>
              )}
              {task.prize && <span>🏆 {task.prize}</span>}
            </div>
            {task.caption && (
              <p style={{ margin: "4px 0 0", fontSize: 13, color: "var(--wp-on-surface-variant)" }}>
                {task.caption}
              </p>
            )}

            {task.qr_token && (
              <div
                className={styles.taskQr}
                aria-label={`Event check-in QR for ${task.title}`}
              >
                <QRCodeSVG value={task.qr_token} size={112} marginSize={2} />
                <span className={styles.taskQrCaption}>Scan to check in</span>
              </div>
            )}
          </div>

          <div className={styles.taskActions}>
            <button
              type="button"
              className={styles.btnGhost}
              onClick={() => onManageItems(task)}
              aria-label={`Assessment items for ${task.title}`}
            >
              Items ({task.assessment_items?.length ?? 0})
            </button>
            <button
              type="button"
              className={styles.btnGhost}
              onClick={() => onManageCheckins(task)}
              aria-label={`Manage check-ins for ${task.title}`}
            >
              Check-ins
            </button>
            <button
              type="button"
              className={styles.btnGhost}
              onClick={() => onEdit(task)}
              aria-label={`Edit ${task.title}`}
            >
              Edit
            </button>
            <button
              type="button"
              className={styles.btnDanger}
              onClick={() => onDelete(task.id)}
              aria-label={`Delete ${task.title}`}
            >
              Delete
            </button>
          </div>
        </li>
      ))}
    </ul>
  );
}

// ---------------------------------------------------------------------------
// Theme editor modal (US-13 / FR-B4)
// ---------------------------------------------------------------------------

// The palette holds ~20 tokens; these are the ones worth a color picker. The rest
// (the on-* contrast pairs especially) stay as authored and remain editable via
// the API, so tuning them is still config rather than code (NFR-6).
const EDITABLE_COLORS: { key: string; label: string }[] = [
  { key: "primary", label: "Primary" },
  { key: "secondary", label: "Secondary" },
  { key: "hero-a", label: "Hero top" },
  { key: "hero-b", label: "Hero bottom" },
];

function ThemeEditorModal({
  themeId,
  onClose,
  onSaved,
}: {
  themeId: string;
  onClose: () => void;
  onSaved: () => void;
}) {
  const [theme, setTheme] = useState<Theme | null>(null);
  const [colors, setColors] = useState<Record<string, string>>({});
  const [appTitle, setAppTitle] = useState("");
  const [tagline, setTagline] = useState("");
  const [copyTone, setCopyTone] = useState("");
  const [logoUrl, setLogoUrl] = useState("");
  const [heroUrl, setHeroUrl] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    void themeApi
      .getTheme(themeId)
      .then((t) => {
        setTheme(t);
        setColors(
          Object.fromEntries(
            EDITABLE_COLORS.map(({ key }) => [key, t.palette[key] ?? "#000000"]),
          ),
        );
        setAppTitle(t.app_title);
        setTagline(t.tagline);
        setCopyTone(t.copy_tone);
        setLogoUrl(t.logo_url ?? "");
        setHeroUrl(t.hero_url ?? "");
      })
      .catch((e) =>
        setError(e instanceof api.ApiError ? e.message : "Could not load theme"),
      );
  }, [themeId]);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!theme) return;
    setError(null);
    setSaving(true);
    try {
      // Merge into the fetched palette: the API replaces the map wholesale, so
      // sending only the edited keys would drop every token not shown here.
      await themeApi.updateTheme(theme.id, {
        palette: { ...theme.palette, ...colors },
        app_title: appTitle,
        tagline,
        copy_tone: copyTone,
        logo_url: logoUrl || null,
        hero_url: heroUrl || null,
      });
      onSaved();
    } catch (err) {
      setError(err instanceof api.ApiError ? err.message : "Save failed");
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className={styles.overlay} role="dialog" aria-modal="true" aria-label="Theme editor">
      <div className={`${styles.modal} ${styles.modalWide}`}>
        <h2>Edit theme{theme ? `: ${theme.name}` : ""}</h2>
        {error && <p className={styles.error}>{error}</p>}
        {!theme ? (
          <p className={styles.empty}>Loading…</p>
        ) : (
          <form onSubmit={(e) => void handleSubmit(e)}>
            <div className={styles.colorGrid}>
              {EDITABLE_COLORS.map(({ key, label }) => (
                <div key={key} className={styles.colorField}>
                  <label htmlFor={`te-${key}`}>{label}</label>
                  <input
                    id={`te-${key}`}
                    type="color"
                    value={colors[key] ?? "#000000"}
                    onChange={(e) =>
                      setColors((prev) => ({ ...prev, [key]: e.target.value }))
                    }
                  />
                </div>
              ))}
            </div>
            <div className={styles.fieldGroup}>
              <label htmlFor="te-app-title">App title</label>
              <input
                id="te-app-title"
                type="text"
                value={appTitle}
                onChange={(e) => setAppTitle(e.target.value)}
                required
              />
            </div>
            <div className={styles.fieldGroup}>
              <label htmlFor="te-tagline">Tagline</label>
              <textarea
                id="te-tagline"
                rows={2}
                value={tagline}
                onChange={(e) => setTagline(e.target.value)}
                placeholder="Shown to students under the countdown"
              />
            </div>
            <div className={styles.fieldGroup}>
              <label htmlFor="te-copy-tone">Copy tone</label>
              <input
                id="te-copy-tone"
                type="text"
                value={copyTone}
                onChange={(e) => setCopyTone(e.target.value)}
                placeholder="e.g. dark, retro-80s, ominous"
              />
            </div>
            <div className={styles.fieldGroup}>
              <label htmlFor="te-logo-url">Logo URL</label>
              <input
                id="te-logo-url"
                type="url"
                value={logoUrl}
                onChange={(e) => setLogoUrl(e.target.value)}
                placeholder="https://…  (optional)"
              />
            </div>
            <div className={styles.fieldGroup}>
              <label htmlFor="te-hero-url">Hero art URL</label>
              <input
                id="te-hero-url"
                type="url"
                value={heroUrl}
                onChange={(e) => setHeroUrl(e.target.value)}
                placeholder="https://…  (optional)"
              />
            </div>
            <div className={styles.formActions}>
              <button type="button" className={styles.btnSecondary} onClick={onClose}>
                Cancel
              </button>
              <button type="submit" className={styles.btnPrimary} disabled={saving}>
                {saving ? "Saving…" : "Save theme"}
              </button>
            </div>
          </form>
        )}
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Challenge create / edit modal
// ---------------------------------------------------------------------------

function ChallengeFormModal({
  existing,
  onClose,
  onSaved,
}: {
  existing?: Challenge;
  onClose: () => void;
  onSaved: (c: Challenge) => void;
}) {
  const [name, setName] = useState(existing?.name ?? "");
  const [semester, setSemester] = useState(existing?.semester ?? "");
  const [startDate, setStartDate] = useState(existing?.start_date ?? "");
  const [endDate, setEndDate] = useState(existing?.end_date ?? "");
  const [themeId, setThemeId] = useState(existing?.theme_id ?? "");
  const [themes, setThemes] = useState<Theme[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);

  // A failed lookup just leaves the picker on "Default" — it must not block
  // authoring the rest of the challenge.
  useEffect(() => {
    void themeApi.listThemes().then(setThemes).catch(() => setThemes([]));
  }, []);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setSaving(true);
    try {
      let saved: Challenge;
      if (existing) {
        saved = await api.updateChallenge(existing.id, {
          name, semester, start_date: startDate, end_date: endDate, theme_id: themeId,
        });
      } else {
        saved = await api.createChallenge({
          name, semester, start_date: startDate, end_date: endDate, theme_id: themeId,
        });
      }
      onSaved(saved);
    } catch (err) {
      setError(err instanceof api.ApiError ? err.message : "Save failed");
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className={styles.overlay} role="dialog" aria-modal="true" aria-label="Challenge form">
      <div className={styles.modal}>
        <h2>{existing ? "Edit challenge" : "New challenge"}</h2>
        {error && <p className={styles.error}>{error}</p>}
        <form onSubmit={(e) => void handleSubmit(e)}>
          <div className={styles.fieldGroup}>
            <label htmlFor="cf-name">Challenge name</label>
            <input
              id="cf-name"
              type="text"
              value={name}
              onChange={(e) => setName(e.target.value)}
              required
              placeholder="e.g. Fall 2025 Wellness"
            />
          </div>
          <div className={styles.fieldGroup}>
            <label htmlFor="cf-semester">Semester</label>
            <input
              id="cf-semester"
              type="text"
              value={semester}
              onChange={(e) => setSemester(e.target.value)}
              required
              placeholder="e.g. Fall 2025"
            />
          </div>
          <div className={styles.fieldGroup}>
            <label htmlFor="cf-theme">Theme</label>
            <select
              id="cf-theme"
              value={themeId}
              onChange={(e) => setThemeId(e.target.value)}
            >
              <option value="">Default</option>
              {themes.map((t) => (
                <option key={t.id} value={t.id}>
                  {t.name}
                </option>
              ))}
            </select>
            <p className={styles.fieldHint}>
              Skins the student app. Switching themes needs no code change.
            </p>
          </div>
          <div className={`${styles.fieldGroup} ${styles.fieldRow}`}>
            <div>
              <label htmlFor="cf-start">Start date</label>
              <input
                id="cf-start"
                type="date"
                value={startDate}
                onChange={(e) => setStartDate(e.target.value)}
                required
              />
            </div>
            <div>
              <label htmlFor="cf-end">End date</label>
              <input
                id="cf-end"
                type="date"
                value={endDate}
                onChange={(e) => setEndDate(e.target.value)}
                required
              />
            </div>
          </div>
          <div className={styles.formActions}>
            <button type="button" className={styles.btnSecondary} onClick={onClose}>
              Cancel
            </button>
            <button type="submit" className={styles.btnPrimary} disabled={saving}>
              {saving ? "Saving…" : existing ? "Save changes" : "Create challenge"}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Task create / edit modal
// ---------------------------------------------------------------------------

function TaskFormModal({
  challengeId,
  existing,
  onClose,
  onSaved,
}: {
  challengeId: number;
  existing?: Task;
  onClose: () => void;
  onSaved: () => void;
}) {
  const [title, setTitle] = useState(existing?.title ?? "");
  const [caption, setCaption] = useState(existing?.caption ?? "");
  const [activityType, setActivityType] = useState(existing?.activity_type ?? "");
  const [location, setLocation] = useState(existing?.location ?? "");
  const [windowStart, setWindowStart] = useState(existing?.date_window_start ?? "");
  const [windowEnd, setWindowEnd] = useState(existing?.date_window_end ?? "");
  const [prize, setPrize] = useState(existing?.prize ?? "");
  const [required, setRequired] = useState(existing?.required ?? true);
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setSaving(true);
    const payload = {
      title,
      caption,
      activity_type: activityType,
      location,
      date_window_start: windowStart || null,
      date_window_end: windowEnd || null,
      prize,
      required,
    };
    try {
      if (existing) {
        await api.updateTask(challengeId, existing.id, payload);
      } else {
        await api.addTask(challengeId, payload);
      }
      onSaved();
    } catch (err) {
      setError(err instanceof api.ApiError ? err.message : "Save failed");
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className={styles.overlay} role="dialog" aria-modal="true" aria-label="Task form">
      <div className={styles.modal}>
        <h2>{existing ? "Edit task" : "Add task"}</h2>
        {error && <p className={styles.error}>{error}</p>}
        <form onSubmit={(e) => void handleSubmit(e)}>
          <div className={styles.fieldGroup}>
            <label htmlFor="tf-title">Title</label>
            <input
              id="tf-title"
              type="text"
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              required
              placeholder="e.g. Week 1 – Vision Check"
            />
          </div>
          <div className={styles.fieldGroup}>
            <label htmlFor="tf-caption">Caption</label>
            <textarea
              id="tf-caption"
              value={caption}
              onChange={(e) => setCaption(e.target.value)}
              placeholder="Short description shown to students"
            />
          </div>
          <div className={`${styles.fieldGroup} ${styles.fieldRow}`}>
            <div>
              <label htmlFor="tf-type">Activity type</label>
              <input
                id="tf-type"
                type="text"
                value={activityType}
                onChange={(e) => setActivityType(e.target.value)}
                placeholder="e.g. health_screening"
              />
            </div>
            <div>
              <label htmlFor="tf-location">Location</label>
              <input
                id="tf-location"
                type="text"
                value={location}
                onChange={(e) => setLocation(e.target.value)}
                placeholder="e.g. SHS Lobby"
              />
            </div>
          </div>
          <div className={`${styles.fieldGroup} ${styles.fieldRow}`}>
            <div>
              <label htmlFor="tf-wstart">Window start</label>
              <input
                id="tf-wstart"
                type="date"
                value={windowStart}
                onChange={(e) => setWindowStart(e.target.value)}
              />
            </div>
            <div>
              <label htmlFor="tf-wend">Window end</label>
              <input
                id="tf-wend"
                type="date"
                value={windowEnd}
                onChange={(e) => setWindowEnd(e.target.value)}
              />
            </div>
          </div>
          <div className={styles.fieldGroup}>
            <label htmlFor="tf-prize">Prize</label>
            <input
              id="tf-prize"
              type="text"
              value={prize}
              onChange={(e) => setPrize(e.target.value)}
              placeholder="e.g. Raffle entry"
            />
          </div>
          <div className={styles.fieldGroup}>
            <div className={styles.checkRow}>
              <input
                id="tf-required"
                type="checkbox"
                checked={required}
                onChange={(e) => setRequired(e.target.checked)}
              />
              <label htmlFor="tf-required" style={{ fontWeight: "normal" }}>
                Required task (counts toward prize eligibility)
              </label>
            </div>
          </div>
          <div className={styles.formActions}>
            <button type="button" className={styles.btnSecondary} onClick={onClose}>
              Cancel
            </button>
            <button type="submit" className={styles.btnPrimary} disabled={saving}>
              {saving ? "Saving…" : existing ? "Save changes" : "Add task"}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Assessment items panel (FR-B3 / US-12)
// ---------------------------------------------------------------------------

function AssessmentItemsPanel({
  challengeId,
  task,
  onClose,
}: {
  challengeId: number;
  task: Task;
  onClose: () => void;
}) {
  const [items, setItems] = useState<AssessmentItem[]>(
    task.assessment_items ?? [],
  );
  const [showForm, setShowForm] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleDelete(itemId: number) {
    try {
      await api.deleteAssessmentItem(challengeId, task.id, itemId);
      setItems((prev) => prev.filter((i) => i.id !== itemId));
    } catch (err) {
      setError(
        err instanceof api.ApiError ? err.message : "Delete failed",
      );
    }
  }

  function handleAdded(item: AssessmentItem) {
    setItems((prev) => [...prev, item]);
    setShowForm(false);
  }

  return (
    <div
      className={styles.overlay}
      role="dialog"
      aria-modal="true"
      aria-label={`Assessment items for ${task.title}`}
    >
      <div className={`${styles.modal} ${styles.modalWide}`}>
        <h2>Assessment items — {task.title}</h2>
        {error && <p className={styles.error}>{error}</p>}

        {items.length === 0 && !showForm && (
          <p className={styles.empty}>
            No assessment items yet. Add an MCQ or reflection.
          </p>
        )}

        {items.length > 0 && (
          <ul className={styles.itemList} aria-label="Assessment items">
            {items.map((item) => (
              <li key={item.id} className={styles.assessmentItem}>
                <div className={styles.itemBody}>
                  <span className={styles.itemTypeBadge}>
                    {item.item_type === "mcq" ? "MCQ" : "Reflection"}
                  </span>
                  <span className={styles.outcomeBadge}>
                    {item.outcome_tag}
                  </span>
                  <p className={styles.itemPrompt}>{item.prompt}</p>
                  {item.item_type === "mcq" && item.options && (
                    <div className={styles.itemMeta}>
                      Options: {item.options.join(", ")} · Answer:{" "}
                      <strong>{item.answer_key}</strong>
                    </div>
                  )}
                  {item.item_type === "reflection" && item.rubric && (
                    <div className={styles.itemMeta}>
                      Rubric: {item.rubric}
                    </div>
                  )}
                </div>
                <button
                  type="button"
                  className={styles.btnDanger}
                  onClick={() => void handleDelete(item.id)}
                  aria-label={`Delete assessment item: ${item.prompt.slice(0, 30)}`}
                >
                  Delete
                </button>
              </li>
            ))}
          </ul>
        )}

        {showForm && (
          <AssessmentItemFormModal
            challengeId={challengeId}
            taskId={task.id}
            onCancel={() => setShowForm(false)}
            onSaved={handleAdded}
          />
        )}

        <div className={styles.formActions}>
          {!showForm && (
            <button
              type="button"
              className={styles.btnSecondary}
              onClick={() => setShowForm(true)}
            >
              + Add item
            </button>
          )}
          <button
            type="button"
            className={styles.btnPrimary}
            onClick={onClose}
          >
            Done
          </button>
        </div>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Assessment item form (inline in panel)
// ---------------------------------------------------------------------------

function AssessmentItemFormModal({
  challengeId,
  taskId,
  onCancel,
  onSaved,
}: {
  challengeId: number;
  taskId: number;
  onCancel: () => void;
  onSaved: (item: AssessmentItem) => void;
}) {
  const [itemType, setItemType] = useState<"mcq" | "reflection">("mcq");
  const [prompt, setPrompt] = useState("");
  const [outcomeTag, setOutcomeTag] = useState("");
  // MCQ
  const [options, setOptions] = useState(["", ""]);
  const [answerKey, setAnswerKey] = useState("");
  // Reflection
  const [rubric, setRubric] = useState("");

  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);

  function addOption() {
    setOptions((prev) => [...prev, ""]);
  }

  function updateOption(idx: number, value: string) {
    setOptions((prev) => prev.map((o, i) => (i === idx ? value : o)));
  }

  function removeOption(idx: number) {
    if (options.length <= 2) return;
    setOptions((prev) => prev.filter((_, i) => i !== idx));
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setSaving(true);
    try {
      let item: AssessmentItem;
      if (itemType === "mcq") {
        const cleaned = options.map((o) => o.trim()).filter(Boolean);
        if (cleaned.length < 2) {
          setError("At least 2 non-empty options are required");
          setSaving(false);
          return;
        }
        if (!cleaned.includes(answerKey.trim())) {
          setError("Answer key must match one of the options");
          setSaving(false);
          return;
        }
        item = await api.addAssessmentItem(challengeId, taskId, {
          item_type: "mcq",
          prompt,
          outcome_tag: outcomeTag,
          options: cleaned,
          answer_key: answerKey.trim(),
        });
      } else {
        item = await api.addAssessmentItem(challengeId, taskId, {
          item_type: "reflection",
          prompt,
          outcome_tag: outcomeTag,
          rubric,
        });
      }
      onSaved(item);
    } catch (err) {
      setError(err instanceof api.ApiError ? err.message : "Save failed");
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className={styles.itemForm}>
      <h3>New {itemType === "mcq" ? "MCQ" : "Reflection"}</h3>
      {error && <p className={styles.error}>{error}</p>}
      <form onSubmit={(e) => void handleSubmit(e)}>
        <div className={styles.fieldGroup}>
          <label htmlFor="ai-type">Item type</label>
          <select
            id="ai-type"
            value={itemType}
            onChange={(e) =>
              setItemType(e.target.value as "mcq" | "reflection")
            }
          >
            <option value="mcq">Multiple choice (MCQ)</option>
            <option value="reflection">Reflection</option>
          </select>
        </div>
        <div className={styles.fieldGroup}>
          <label htmlFor="ai-prompt">Prompt</label>
          <textarea
            id="ai-prompt"
            value={prompt}
            onChange={(e) => setPrompt(e.target.value)}
            required
            placeholder="Question or reflection prompt shown to students"
          />
        </div>
        <div className={styles.fieldGroup}>
          <label htmlFor="ai-outcome">Learning outcome tag</label>
          <input
            id="ai-outcome"
            type="text"
            value={outcomeTag}
            onChange={(e) => setOutcomeTag(e.target.value)}
            required
            placeholder="e.g. sleep-hygiene, nutrition, mental-health"
          />
        </div>

        {itemType === "mcq" && (
          <>
            <div className={styles.fieldGroup}>
              <label>Options (min 2)</label>
              {options.map((opt, idx) => (
                <div key={idx} className={styles.optionRow}>
                  <input
                    type="text"
                    value={opt}
                    onChange={(e) => updateOption(idx, e.target.value)}
                    placeholder={`Option ${idx + 1}`}
                    required
                  />
                  {options.length > 2 && (
                    <button
                      type="button"
                      className={styles.btnDanger}
                      onClick={() => removeOption(idx)}
                      aria-label={`Remove option ${idx + 1}`}
                    >
                      x
                    </button>
                  )}
                </div>
              ))}
              <button
                type="button"
                className={styles.btnGhost}
                onClick={addOption}
              >
                + Add option
              </button>
            </div>
            <div className={styles.fieldGroup}>
              <label htmlFor="ai-answer">Answer key</label>
              <select
                id="ai-answer"
                value={answerKey}
                onChange={(e) => setAnswerKey(e.target.value)}
                required
              >
                <option value="">— select correct answer —</option>
                {options
                  .filter((o) => o.trim() !== "")
                  .map((o) => (
                    <option key={o} value={o.trim()}>
                      {o.trim()}
                    </option>
                  ))}
              </select>
            </div>
          </>
        )}

        {itemType === "reflection" && (
          <div className={styles.fieldGroup}>
            <label htmlFor="ai-rubric">Rubric</label>
            <textarea
              id="ai-rubric"
              value={rubric}
              onChange={(e) => setRubric(e.target.value)}
              required
              placeholder="Scoring criteria, e.g. 1 – vague; 2 – specific; 3 – actionable"
            />
          </div>
        )}

        <div className={styles.formActions}>
          <button
            type="button"
            className={styles.btnSecondary}
            onClick={onCancel}
          >
            Cancel
          </button>
          <button
            type="submit"
            className={styles.btnPrimary}
            disabled={saving}
          >
            {saving ? "Saving…" : "Add item"}
          </button>
        </div>
      </form>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Root component
// ---------------------------------------------------------------------------

export function ChallengeBuilder() {
  const { session, signOut } = useSession();
  const [view, setView] = useState<View>({ kind: "list" });

  return (
    <div className={styles.page}>
      <header className={styles.topbar}>
        <h1>Challenge Builder</h1>
        <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
          {session && (
            <span style={{ fontSize: 13, color: "var(--wp-on-surface-variant)" }}>
              {session.affiliation}
            </span>
          )}
          <button
            type="button"
            className={styles.btnSecondary}
            onClick={() => void signOut()}
          >
            Sign out
          </button>
        </div>
      </header>

      <main className={styles.content}>
        {view.kind === "list" && (
          <ChallengeList
            onOpen={(id) => setView({ kind: "detail", id })}
            onCreated={(id) => setView({ kind: "detail", id })}
          />
        )}
        {view.kind === "detail" && (
          <ChallengeDetail
            id={view.id}
            onBack={() => setView({ kind: "list" })}
          />
        )}
      </main>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Manual completion override + audit (FR-D6 / US-27)
// ---------------------------------------------------------------------------

function fmtTs(ts: string) {
  const d = new Date(ts);
  return Number.isNaN(d.getTime())
    ? ts
    : d.toLocaleString(undefined, {
        month: "short",
        day: "numeric",
        hour: "numeric",
        minute: "2-digit",
      });
}

/**
 * Admin surface for FR-D6: mark a student complete by hand, correct an
 * erroneous check-in, or remove one — each write leaving an audit row.
 *
 * Fetches on mount rather than reading off the task (as AssessmentItemsPanel
 * does): TaskOut deliberately carries no check-ins array, since that would be an
 * unbounded per-task payload on every builder load.
 */
function CompletionOverridePanel({
  challengeId,
  task,
  onClose,
}: {
  challengeId: number;
  task: Task;
  onClose: () => void;
}) {
  const [tab, setTab] = useState<"checkins" | "audit">("checkins");
  const [checkins, setCheckins] = useState<CheckIn[]>([]);
  const [audits, setAudits] = useState<CheckInAudit[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [adding, setAdding] = useState(false);
  // The check-in awaiting a removal reason, if any.
  const [removing, setRemoving] = useState<CheckIn | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const [c, a] = await Promise.all([
        api.listCheckIns(challengeId, task.id),
        api.listCheckInAudits(challengeId, task.id),
      ]);
      setCheckins(c);
      setAudits(a);
      setError(null);
    } catch (err) {
      setError(err instanceof api.ApiError ? err.message : "Could not load check-ins");
    } finally {
      setLoading(false);
    }
  }, [challengeId, task.id]);

  useEffect(() => { void load(); }, [load]);

  async function handleRemove(reason: string) {
    if (!removing) return;
    try {
      await api.removeCheckIn(challengeId, task.id, removing.id, { reason });
      setRemoving(null);
      await load();
    } catch (err) {
      setError(err instanceof api.ApiError ? err.message : "Remove failed");
    }
  }

  return (
    <div
      className={styles.overlay}
      role="dialog"
      aria-modal="true"
      aria-label={`Check-ins for ${task.title}`}
    >
      <div
        className={`${styles.modal} ${styles.modalWide} ${styles.overridePanel}`}
      >
        <h2>Check-ins — {task.title}</h2>
        {error && <p className={styles.error}>{error}</p>}

        <div className={styles.tabRow} role="tablist">
          <button
            type="button"
            role="tab"
            aria-selected={tab === "checkins"}
            className={tab === "checkins" ? styles.tabBtnActive : styles.tabBtn}
            onClick={() => setTab("checkins")}
          >
            Check-ins ({checkins.length})
          </button>
          <button
            type="button"
            role="tab"
            aria-selected={tab === "audit"}
            className={tab === "audit" ? styles.tabBtnActive : styles.tabBtn}
            onClick={() => setTab("audit")}
          >
            Audit ({audits.length})
          </button>
        </div>

        {loading && <p className={styles.empty}>Loading…</p>}

        {!loading && tab === "checkins" && (
          <>
            {checkins.length === 0 && !adding && (
              <p className={styles.empty}>
                No check-ins for this task yet.
              </p>
            )}

            {checkins.length > 0 && (
              <ul className={styles.checkinList} aria-label="Check-ins">
                {checkins.map((c) => (
                  <li key={c.id} className={styles.checkinRow}>
                    <span className={styles.checkinSubject}>{c.student_subject}</span>
                    <div className={styles.checkinMeta}>
                      <span className={styles.methodBadge}>{c.method}</span>
                      <span>{fmtTs(c.ts)}</span>
                    </div>
                    {c.verified_by && (
                      <div className={styles.checkinMeta}>by {c.verified_by}</div>
                    )}
                    {removing?.id === c.id ? (
                      <ReasonPrompt
                        label={`Remove the check-in for ${c.student_subject}`}
                        submitLabel="Remove"
                        onCancel={() => setRemoving(null)}
                        onSubmit={handleRemove}
                      />
                    ) : (
                      <div className={styles.checkinActions}>
                        <button
                          type="button"
                          className={styles.btnDanger}
                          onClick={() => setRemoving(c)}
                          aria-label={`Remove check-in for ${c.student_subject}`}
                        >
                          Remove
                        </button>
                      </div>
                    )}
                  </li>
                ))}
              </ul>
            )}

            {adding ? (
              <ManualCheckInForm
                challengeId={challengeId}
                taskId={task.id}
                onCancel={() => setAdding(false)}
                onSaved={() => { setAdding(false); void load(); }}
              />
            ) : (
              <button
                type="button"
                className={styles.btnSecondary}
                onClick={() => { setError(null); setAdding(true); }}
              >
                + Mark complete
              </button>
            )}
          </>
        )}

        {!loading && tab === "audit" && (
          <>
            {audits.length === 0 && (
              <p className={styles.empty}>No changes recorded yet.</p>
            )}
            {audits.length > 0 && (
              <ul className={styles.auditList} aria-label="Audit trail">
                {audits.map((a) => (
                  <li key={a.id} className={styles.auditRow}>
                    <div className={styles.checkinMeta}>
                      <span className={`${styles.actionBadge} ${actionClass(a.action)}`}>
                        {a.action}
                      </span>
                      <span>{fmtTs(a.ts)}</span>
                    </div>
                    <div className={styles.checkinMeta}>by {a.actor_subject}</div>
                    <p className={styles.auditReason}>{a.reason}</p>
                    {a.prior_state && (
                      <details>
                        <summary>Prior state</summary>
                        <pre className={styles.auditSnapshot}>
                          {JSON.stringify(a.prior_state, null, 2)}
                        </pre>
                      </details>
                    )}
                  </li>
                ))}
              </ul>
            )}
          </>
        )}

        <div className={styles.formActions}>
          <button type="button" className={styles.btnPrimary} onClick={onClose}>
            Done
          </button>
        </div>
      </div>
    </div>
  );
}

function actionClass(action: CheckInAudit["action"]) {
  if (action === "create") return styles.actionCreate;
  if (action === "update") return styles.actionUpdate;
  return styles.actionDelete;
}

/** Inline reason capture. Not window.confirm — a reason is mandatory (FR-D6). */
function ReasonPrompt({
  label,
  submitLabel,
  onCancel,
  onSubmit,
}: {
  label: string;
  submitLabel: string;
  onCancel: () => void;
  onSubmit: (reason: string) => void | Promise<void>;
}) {
  const [reason, setReason] = useState("");
  const [saving, setSaving] = useState(false);
  const blank = reason.trim() === "";

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (blank) return;
    setSaving(true);
    try {
      await onSubmit(reason.trim());
    } finally {
      setSaving(false);
    }
  }

  return (
    <form className={styles.itemForm} onSubmit={(e) => void handleSubmit(e)}>
      <div className={styles.fieldGroup}>
        <label htmlFor="removeReason">{label} — reason</label>
        <textarea
          id="removeReason"
          rows={2}
          value={reason}
          onChange={(e) => setReason(e.target.value)}
          placeholder="Why is this change being made?"
          required
        />
      </div>
      <div className={styles.formActions}>
        <button type="button" className={styles.btnSecondary} onClick={onCancel}>
          Cancel
        </button>
        <button type="submit" className={styles.btnDanger} disabled={saving || blank}>
          {saving ? "Working…" : submitLabel}
        </button>
      </div>
    </form>
  );
}

function ManualCheckInForm({
  challengeId,
  taskId,
  onCancel,
  onSaved,
}: {
  challengeId: number;
  taskId: number;
  onCancel: () => void;
  onSaved: () => void;
}) {
  const [subject, setSubject] = useState("");
  const [reason, setReason] = useState("");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const incomplete = subject.trim() === "" || reason.trim() === "";

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (incomplete) return;
    setSaving(true);
    setError(null);
    try {
      await api.createManualCheckIn(challengeId, taskId, {
        student_subject: subject.trim(),
        reason: reason.trim(),
      });
      onSaved();
    } catch (err) {
      setError(err instanceof api.ApiError ? messageFor(err) : "Save failed");
    } finally {
      setSaving(false);
    }
  }

  return (
    <form className={styles.itemForm} onSubmit={(e) => void handleSubmit(e)}>
      {error && <p className={styles.error}>{error}</p>}
      <div className={styles.fieldGroup}>
        <label htmlFor="studentSubject">Student SSO subject</label>
        <input
          id="studentSubject"
          type="text"
          inputMode="email"
          autoComplete="off"
          value={subject}
          onChange={(e) => setSubject(e.target.value)}
          placeholder="student@csub.edu"
          required
        />
      </div>
      <div className={styles.fieldGroup}>
        <label htmlFor="manualReason">Reason</label>
        <textarea
          id="manualReason"
          rows={2}
          value={reason}
          onChange={(e) => setReason(e.target.value)}
          placeholder="Why is this being marked by hand?"
          required
        />
      </div>
      <div className={styles.formActions}>
        <button type="button" className={styles.btnSecondary} onClick={onCancel}>
          Cancel
        </button>
        <button type="submit" className={styles.btnPrimary} disabled={saving || incomplete}>
          {saving ? "Saving…" : "Mark complete"}
        </button>
      </div>
    </form>
  );
}

/** Turn the API's 409/404 into something an admin at a booth can act on. */
function messageFor(err: InstanceType<typeof api.ApiError>) {
  if (err.status === 409) {
    return "That student is already checked in for this task — use Remove, then re-add.";
  }
  return err.message;
}
