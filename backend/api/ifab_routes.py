from flask import Blueprint, request, jsonify
from . import db

from rag import config

import os
from os import listdir
from os.path import isfile, join

ifab_bp = Blueprint('ifab', __name__)

@ifab_bp.route('/ifabs', methods=['GET'])
def list_ifabs_docs():
    """List all PDF files in the IFAB directory."""
    try:
        files = [
            f for f in listdir(config.IFAB_DIR)
            if isfile(join(config.IFAB_DIR, f)) and f.lower().endswith('.pdf')
        ]
        return jsonify({'files': files}), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@ifab_bp.route('/ifabs/<filename>', methods=['GET'])
def get_ifab_doc(filename):
    """Retrieve a specific PDF file from the IFAB directory."""
    try:
        file_path = join(config.IFAB_DIR, filename)
        if not isfile(file_path):
            return jsonify({'error': 'File not found'}), 404

        with open(file_path, 'rb') as f:
            content = f.read()

        return content, 200, {
            'Content-Type': 'application/pdf',
            'Content-Disposition': f'inline; filename="{filename}"'
        }
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@ifab_bp.route('/ifabs', methods=['POST'])
def upload_ifab_doc():
    """Upload a new PDF file to the IFAB directory."""
    try:
        if 'file' not in request.files:
            return jsonify({'error': 'No file part in the request'}), 400

        file = request.files['file']
        if file.filename == '':
            return jsonify({'error': 'No selected file'}), 400

        if not file.filename.lower().endswith('.pdf'):
            return jsonify({'error': 'Only PDF files are allowed'}), 400

        file_path = join(config.IFAB_DIR, file.filename)
        file.save(file_path)

        return jsonify({'msg': f'File {file.filename} uploaded successfully'}), 201
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@ifab_bp.route('/ifabs/<filename>', methods=['DELETE'])
def delete_ifab_doc(filename):
    """Delete a specific PDF file from the IFAB directory."""
    try:
        file_path = join(config.IFAB_DIR, filename)
        if not isfile(file_path):
            return jsonify({'error': 'File not found'}), 404

        os.remove(file_path)
        return jsonify({'msg': f'File {filename} deleted successfully'}), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500
