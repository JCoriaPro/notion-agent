import os
import logging
import requests
from flask import Flask, request, render_template, jsonify, flash, redirect, url_for

# Configure logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

app = Flask(__name__)
app.secret_key = os.environ.get("SESSION_SECRET", "dev-secret-key")

# Notion API configuration
NOTION_TOKEN = os.environ.get('NOTION_TOKEN')
PAGE_ID = os.environ.get('NOTION_PAGE_ID', '2020b70967ed803ba28fdc5ed49984a0')
NOTION_VERSION = "2022-06-28"

def format_uuid(raw):
    """Format a raw UUID string into proper UUID format"""
    if len(raw) != 32:
        logger.error(f"Invalid UUID length: {len(raw)}, expected 32")
        return None
    return f"{raw[0:8]}-{raw[8:12]}-{raw[12:16]}-{raw[16:20]}-{raw[20:]}"

def validate_notion_config():
    """Validate that Notion configuration is present"""
    if not NOTION_TOKEN:
        return False, "NOTION_TOKEN environment variable is required"
    if not PAGE_ID:
        return False, "NOTION_PAGE_ID environment variable is required"
    return True, "Configuration valid"

@app.route('/')
def index():
    """Main page with note writing interface"""
    config_valid, config_message = validate_notion_config()
    return render_template('index.html', 
                         config_valid=config_valid, 
                         config_message=config_message)

@app.route('/write', methods=['POST'])
def write_note():
    """API endpoint to write a note to Notion page"""
    try:
        # Validate configuration
        config_valid, config_message = validate_notion_config()
        if not config_valid:
            logger.error(f"Configuration error: {config_message}")
            return jsonify({"status": "error", "message": config_message}), 400

        # Get content from request
        if request.is_json:
            content = request.json.get('content', '').strip()
        else:
            content = request.form.get('content', '').strip()

        if not content:
            logger.warning("Empty content provided")
            return jsonify({"status": "error", "message": "Content cannot be empty"}), 400

        # Format the page ID as UUID
        block_id = format_uuid(PAGE_ID)
        if not block_id:
            logger.error(f"Failed to format PAGE_ID: {PAGE_ID}")
            return jsonify({"status": "error", "message": "Invalid PAGE_ID format"}), 400

        # Prepare Notion API request
        url = f"https://api.notion.com/v1/blocks/{block_id}/children"
        headers = {
            "Authorization": f"Bearer {NOTION_TOKEN}",
            "Content-Type": "application/json",
            "Notion-Version": NOTION_VERSION
        }

        data = {
            "children": [
                {
                    "object": "block",
                    "type": "paragraph",
                    "paragraph": {
                        "rich_text": [
                            {
                                "type": "text",
                                "text": {"content": content}
                            }
                        ]
                    }
                }
            ]
        }

        logger.info(f"Sending note to Notion: {content[:50]}...")
        
        # Make request to Notion API
        response = requests.patch(url, headers=headers, json=data, timeout=10)
        
        if response.status_code == 200:
            logger.info("Note successfully written to Notion")
            if request.is_json:
                return jsonify({"status": "success", "message": "Note written successfully"}), 200
            else:
                flash("Note written successfully!", "success")
                return redirect(url_for('index'))
        else:
            error_detail = response.text
            logger.error(f"Notion API error: {response.status_code} - {error_detail}")
            error_message = f"Failed to write note to Notion: {response.status_code}"
            
            if request.is_json:
                return jsonify({"status": "error", "message": error_message}), response.status_code
            else:
                flash(f"Error: {error_message}", "error")
                return redirect(url_for('index'))

    except requests.exceptions.Timeout:
        logger.error("Timeout while connecting to Notion API")
        error_message = "Request timeout - Notion API did not respond in time"
        if request.is_json:
            return jsonify({"status": "error", "message": error_message}), 408
        else:
            flash(f"Error: {error_message}", "error")
            return redirect(url_for('index'))
            
    except requests.exceptions.ConnectionError:
        logger.error("Connection error while connecting to Notion API")
        error_message = "Connection error - Unable to reach Notion API"
        if request.is_json:
            return jsonify({"status": "error", "message": error_message}), 503
        else:
            flash(f"Error: {error_message}", "error")
            return redirect(url_for('index'))
            
    except Exception as e:
        logger.error(f"Unexpected error: {str(e)}")
        error_message = "An unexpected error occurred"
        if request.is_json:
            return jsonify({"status": "error", "message": error_message}), 500
        else:
            flash(f"Error: {error_message}", "error")
            return redirect(url_for('index'))

@app.route('/health')
def health_check():
    """Health check endpoint"""
    config_valid, config_message = validate_notion_config()
    return jsonify({
        "status": "healthy",
        "notion_configured": config_valid,
        "message": config_message
    })

if __name__ == '__main__':
    app.run(host="0.0.0.0", port=5000, debug=True)
