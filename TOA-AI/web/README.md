# TOA-AI Web Interface

A responsive web interface for the Technical Order Assistant AI (TOA-AI) system, allowing users to easily query and retrieve information from Air Force Technical Orders.

## Features

- **Intuitive Chat Interface**: Simple chat-based interface for asking questions about technical orders
- **Source Attribution**: All responses include proper attribution to Robins Air Force Base and specific Technical Orders
- **Table Display**: Properly formatted tables from Technical Orders
- **Source References**: Sidebar showing all Technical Order references used in the response
- **Responsive Design**: Works on desktop, tablet, and mobile devices
- **Settings Panel**: Toggle visibility of tables and images
- **Error Handling**: Graceful handling of API connectivity issues

## Requirements

- Python 3.8+
- Flask
- Requests
- TOA-AI API running at http://localhost:8000

## Setup

1. Ensure you have installed all required dependencies:
   ```
   pip install -r requirements.txt
   ```

2. Make sure the TOA-AI API server is running:
   ```
   python TOA-AI/api.py
   ```

3. Start the web interface:
   ```
   python TOA-AI/web_app.py
   ```

4. Open your browser and navigate to:
   ```
   http://localhost:5000
   ```

## Usage

1. Enter your question about Air Force Technical Orders in the input field at the bottom of the chat window
2. Press "Send" or hit Enter to submit your question
3. View the response, which will include:
   - Attribution to Robins Air Force Base and relevant Technical Order(s)
   - Formatted answer with proper tables and citations
   - References to specific Technical Orders in the sidebar

## File Structure

- `web_app.py` - Main Flask application
- `web/templates/` - HTML templates
  - `index.html` - Main page template
- `web/static/` - Static assets
  - `css/style.css` - Custom CSS styles
  - `js/main.js` - Client-side JavaScript
  - `img/` - Image assets and cache

## Troubleshooting

If you encounter issues:

1. Ensure the TOA-AI API is running at http://localhost:8000
2. Check the console logs for any JavaScript errors
3. Verify that all required packages are installed
4. Try restarting both the API server and web interface

## Contributing

When contributing to this project, please ensure you follow these guidelines:

1. Keep the UI clean and user-friendly
2. Maintain proper attribution for all Technical Order content
3. Follow the established formatting for tables and references
4. Test on multiple device sizes to ensure responsiveness

## License

This project is proprietary and for internal use only. All rights reserved. 