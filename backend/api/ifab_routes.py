"""Local-demo document endpoints. Do not expose write routes without auth."""
from pathlib import Path

from flask import Blueprint, jsonify, request, send_from_directory
from werkzeug.utils import secure_filename

from rag import config

ifab_bp = Blueprint("ifab", __name__)


@ifab_bp.get("")
@ifab_bp.get("/ifabs")  # compatibility with the original doubled path
def list_ifabs_docs():
    files = sorted(path.name for path in Path(config.IFAB_DIR).glob("*.pdf") if path.is_file())
    return jsonify(files=files)


@ifab_bp.get("/<filename>")
@ifab_bp.get("/ifabs/<filename>")
def get_ifab_doc(filename):
    if not filename.lower().endswith(".pdf"):
        return jsonify(error="Only PDF documents are available"), 404
    return send_from_directory(config.IFAB_DIR, filename, mimetype="application/pdf")


@ifab_bp.post("")
@ifab_bp.post("/ifabs")
def upload_ifab_doc():
    file = request.files.get("file")
    if file is None or not file.filename:
        return jsonify(error="A PDF file is required"), 400
    filename = secure_filename(file.filename)
    if not filename.lower().endswith(".pdf") or file.stream.read(5) != b"%PDF-":
        return jsonify(error="Only valid PDF uploads are allowed"), 400
    file.stream.seek(0)
    path = Path(config.IFAB_DIR, filename)
    if path.exists():
        return jsonify(error="A document with this name already exists; it was not overwritten"), 409
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("xb") as target:
        target.write(file.read())
    return jsonify(msg=f"{filename} uploaded. Run the indexer before using it in explanations."), 201


@ifab_bp.delete("/<filename>")
@ifab_bp.delete("/ifabs/<filename>")
def delete_ifab_doc(filename):
    # Flask's filename converter rejects slashes; also reject special components.
    if Path(filename).name != filename or not filename.lower().endswith(".pdf"):
        return jsonify(error="Document not found"), 404
    path = Path(config.IFAB_DIR, filename)
    if not path.is_file():
        return jsonify(error="Document not found"), 404
    path.unlink()
    return jsonify(msg="PDF removed. Existing indexed passages require a separate index cleanup.")
