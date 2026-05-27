type ItemStatus = "concluído" | "concluido" | "pendente" | "erro" | "rodando" | string;

export type DataTableRow = {
  id: string;
  fileName: string;
  type: string;
  size?: number | null;
  modifiedAt?: string | null;
  status?: ItemStatus;
};

type DataTableProps = {
  rows: DataTableRow[];
  selectedId?: string | null;
  onSelect?: (row: DataTableRow) => void;
  emptyText?: string;
};

function formatSize(size?: number | null) {
  if (!size || size <= 0) return "-";
  const units = ["B", "KB", "MB", "GB"];
  let value = size;
  let unitIndex = 0;
  while (value >= 1024 && unitIndex < units.length - 1) {
    value /= 1024;
    unitIndex += 1;
  }
  return `${value.toFixed(value >= 100 || unitIndex === 0 ? 0 : 1)} ${units[unitIndex]}`;
}

function labelForStatus(status?: ItemStatus) {
  const key = (status ?? "pendente").toLowerCase();
  if (key === "done") return "concluído";
  if (key === "success") return "concluído";
  if (key === "running") return "rodando";
  if (key === "error") return "erro";
  if (key === "pending") return "pendente";
  return key;
}

function classForStatus(status?: ItemStatus) {
  const key = (status ?? "pendente").toLowerCase();
  if (key === "done" || key === "success" || key === "concluído" || key === "concluido") return "status-concluido";
  if (key === "running") return "status-rodando";
  if (key === "error") return "status-erro";
  if (key === "erro") return "status-erro";
  return "status-pendente";
}

export function DataTable({ rows, selectedId, onSelect, emptyText = "Nenhum item encontrado." }: DataTableProps) {
  if (!rows.length) {
    return <div className="data-table-empty">{emptyText}</div>;
  }

  return (
    <table className="data-table" aria-label="Tabela de itens">
      <thead>
        <tr>
          <th>Nome do arquivo</th>
          <th>Tipo</th>
          <th>Tamanho</th>
          <th>Modificação</th>
          <th>Status</th>
        </tr>
      </thead>
      <tbody>
        {rows.map((row) => {
          const selected = selectedId === row.id;
          const statusLabel = labelForStatus(row.status);
          const statusClass = classForStatus(row.status);
          return (
            <tr
              key={row.id}
              className={selected ? "is-selected" : ""}
              onClick={() => onSelect?.(row)}
              aria-selected={selected}
            >
              <td>{row.fileName}</td>
              <td>{row.type}</td>
              <td className="data-table-mono">{formatSize(row.size)}</td>
              <td className="data-table-mono">{row.modifiedAt ?? "-"}</td>
              <td>
                <span className={`status-badge ${statusClass}`}>{statusLabel}</span>
              </td>
            </tr>
          );
        })}
      </tbody>
    </table>
  );
}
