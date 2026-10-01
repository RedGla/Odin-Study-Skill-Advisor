import { useEffect, useRef, useState } from "react";
import { apiClient } from "../api/client";

export default function RenameConversationDialog({ id, title, onClose, onRenamed }: {
  id: string;
  title: string;
  onClose: () => void;
  onRenamed: (title: string) => void;
}) {
  const dialog = useRef<HTMLDialogElement>(null);
  const [name, setName] = useState(title);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => { dialog.current?.showModal(); }, []);

  const save = async (event: React.FormEvent) => {
    event.preventDefault();
    if (!name.trim() || saving) return;
    setSaving(true);
    setError("");
    try {
      const { data } = await apiClient.patch(`/conversations/${id}`, { title: name.trim() });
      onRenamed(data.title);
      onClose();
    } catch {
      setError("Could not rename this conversation. Please try again.");
      setSaving(false);
    }
  };

  return <dialog className="rename-dialog" ref={dialog} onCancel={onClose} aria-labelledby="rename-heading">
    <form onSubmit={save}>
      <p className="dialog-eyebrow">YOUR WORKSPACE</p>
      <h2 id="rename-heading">Rename conversation</h2>
      <label htmlFor="conversation-name">Give this chat a name you’ll recognize.</label>
      <input id="conversation-name" autoFocus required maxLength={120} value={name} onChange={(event) => setName(event.target.value)} />
      {error && <p role="alert" className="form-error">{error}</p>}
      <div className="dialog-actions"><button type="button" className="subtle-button" onClick={onClose}>Cancel</button><button type="submit" className="primary-button" disabled={saving || !name.trim()}>{saving ? "Saving…" : "Save name"}</button></div>
    </form>
  </dialog>;
}
