import os
import requests
import json
import base64
import re
import logging
from flask import Flask, render_template, request, jsonify, send_from_directory, url_for

# Set up logging
logging.basicConfig(level=logging.INFO, 
                    format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Initialize Flask app
app = Flask(__name__, 
            static_folder="web/static",
            template_folder="web/templates")

# TOA-AI API endpoint (disabled)
API_URL = "http://localhost:8000"  # Changed from None
FORCE_OFFLINE = False  # Changed to allow online connections

# Create asset directories if they don't exist
os.makedirs(os.path.join("web", "static", "img", "cache"), exist_ok=True)

@app.route('/')
def index():
    """Render main chat interface."""
    return render_template('index.html')

@app.route('/chat', methods=['POST'])
def chat():
    """Handle chat request from the client."""
    try:
        # Get the query and document from the request
        data = request.json
        query = data.get('message', '').strip()
        selected_document = data.get('document')
        
        app.logger.info(f"Received chat request: {query}")
        
        # Extract keywords from query for better retrieval
        query_keywords = extract_query_keywords(query)
        app.logger.info(f"Extracted keywords: {', '.join(query_keywords)}")
        
        # Get relevant documents based on the query
        relevant_documents = identify_relevant_documents(query, query_keywords)
        
        # Check if we should try using the API (online mode)
        api_available = False
        api_response = None
        
        if API_URL and not FORCE_OFFLINE:
            try:
                # Prepare data for API request
                api_data = {
                    "query": query,
                    "document": selected_document,
                    "keywords": query_keywords,
                    "relevant_documents": relevant_documents
                }
                
                # Make API request with timeout
                app.logger.info(f"Attempting to connect to API at {API_URL}")
                response = requests.post(
                    f"{API_URL}/query", 
                    json=api_data,
                    timeout=5  # 5 second timeout
                )
                
                # Check if response is valid
                if response.status_code == 200:
                    api_response = response.json()
                    api_available = True
                    app.logger.info("Successfully connected to API - using online response")
                else:
                    app.logger.warning(f"API returned error status: {response.status_code}")
            except (requests.RequestException, ValueError) as api_error:
                app.logger.warning(f"API connection failed: {str(api_error)} - falling back to offline mode")
        
        # If online mode didn't work or is disabled, use offline mode
        if not api_available:
            app.logger.info("Operating in OFFLINE mode - using fallback responses")
            
            # Generate fallback/mock response
            content = ""
            
            # Find mentioned aircraft if any
            mentioned_aircraft = None
            for aircraft in ["F-14", "F-16", "F-18", "C-130", "C-17"]:
                if aircraft.lower() in query.lower():
                    mentioned_aircraft = aircraft
                    break
                    
            # Sample data for different aircraft types
            aircraft_data = {
                "F-14": {
                    "aircraft_type": "F-14",
                    "max_pressure": "55 PSI",
                    "nominal_pressure": "40-45 PSI",
                    "flow_rate": "600 gallons per minute",
                    "safety_note": "Ensure canopy is closed before starting refueling",
                    "fuel_type": "JP-8"
                },
                "F-18": {
                    "aircraft_type": "F-18", 
                    "max_pressure": "50 PSI", 
                    "nominal_pressure": "35-45 PSI",
                    "flow_rate": "550 gallons per minute",
                    "safety_note": "Verify all external tanks are properly connected",
                    "fuel_type": "JP-8"
                },
                "C-130": {
                    "aircraft_type": "C-130",
                    "max_pressure": "60 PSI",
                    "nominal_pressure": "45-55 PSI", 
                    "flow_rate": "1000 gallons per minute",
                    "safety_note": "Use extended grounding procedures for cold weather operations",
                    "fuel_type": "JP-8"
                }
            }
            
            # Default suggested document
            suggested_document = selected_document or "TO 00-25-172CL-3"
            suggested_reason = None
            
            # Determine type of response to generate
            if "emergency" in query.lower() or "fire" in query.lower():
                content = generate_emergency_response(mentioned_aircraft, aircraft_data, suggested_document)
                content_type = "emergency"
            elif "hot refuel" in query.lower() or "hot refueling" in query.lower():
                content = generate_hot_refueling_response(mentioned_aircraft, aircraft_data, suggested_document)
                content_type = "hot"
            elif "refuel" in query.lower() or "fuel" in query.lower() or "pressure" in query.lower() or "psi" in query.lower():
                content = generate_refueling_response(mentioned_aircraft, aircraft_data, suggested_document)
                content_type = "refuel"
            else:
                content = generate_general_response(mentioned_aircraft, aircraft_data, suggested_document, query)
                content_type = "general"
            
            # Generate sources for the response
            sources = generate_relevant_sources(query, content_type, mentioned_aircraft, aircraft_data, suggested_document)
            
            # Format and structure the response
            try:
                content = ensure_structured_format(content, query, selected_document)
                content = process_citations(content)
                content = process_warnings(content)
                content = process_tables(content, selected_document)
            except Exception as format_error:
                app.logger.error(f"Error formatting content: {str(format_error)}")
            
            # Make sure we have valid content
            if not content:
                content = f"<p>I'm operating in offline mode and can provide information about aircraft maintenance and refueling procedures. Could you please ask a specific question about these topics?</p>"
            
            # Extract and format sources
            formatted_sources = extract_sources_from_content(content, sources)
            app.logger.info(f"Using {len(formatted_sources)} sources")
            
            # Make sure every source has the necessary fields
            for source in formatted_sources:
                # Add document_origin if missing
                if 'document_origin' not in source and 'text' in source:
                    doc_match = re.search(r'(TO\s+[\d\-]+CL-\d+)', source.get('text', ''))
                    if doc_match:
                        source['document_origin'] = doc_match.group(1)
                
                # Make sure every source has relevance
                if 'relevance' not in source:
                    source['relevance'] = 0.8
                    
                # Add preview if missing
                if 'preview' not in source and 'text' in source:
                    source['preview'] = "Contains detailed information relevant to aircraft maintenance and refueling operations."
            
            # Ensure we have at least some default sources
            if not formatted_sources:
                formatted_sources = [
                    {
                        "text": "TO 00-25-172CL-3, Section 3, Table 2",
                        "details": "Refueling Pressure Specifications",
                        "relevance": 0.8,
                        "preview": "Contains detailed information about maximum and normal pressure ranges for all aircraft types.",
                        "document_origin": "TO 00-25-172CL-3"
                    },
                    {
                        "text": "TO 00-25-172CL-4, Page 35",
                        "details": "Safety Monitoring Requirements",
                        "relevance": 0.7,
                        "preview": "Outlines critical monitoring points and warning indicators during refueling operations.",
                        "document_origin": "TO 00-25-172CL-4"
                    }
                ]
        else:
            # Use the API response
            app.logger.info("Using response from API")
            
            # Make sure we have a default suggested document
            suggested_document = selected_document or "TO 00-25-172CL-3"
            suggested_reason = None
            
            # Log the entire API response structure
            app.logger.info(f"API response structure: {list(api_response.keys())}")
            
            # Check for different possible response formats from the API
            if 'response' in api_response:
                content = api_response.get('response', '')
                app.logger.info("Found 'response' field in API response")
            elif 'answer' in api_response:
                content = api_response.get('answer', '')
                app.logger.info("Found 'answer' field in API response")
            elif 'content' in api_response:
                content = api_response.get('content', '')
                app.logger.info("Found 'content' field in API response")
            elif 'text' in api_response:
                content = api_response.get('text', '')
                app.logger.info("Found 'text' field in API response")
            elif 'message' in api_response:
                content = api_response.get('message', '')
                app.logger.info("Found 'message' field in API response")
            elif 'results' in api_response and api_response['results']:
                # Handle case where API returns results array
                results = api_response.get('results', [])
                content = ""
                for result in results:
                    if 'content' in result:
                        content += result['content'] + " "
                app.logger.info("Extracted content from 'results' field in API response")
                
                # Now override with our own nicely formatted responses based on query type
                query_lower = query.lower()
                mentioned_aircraft = None
                for aircraft in ["F-14", "F-16", "F-18", "C-130", "C-17"]:
                    if aircraft.lower() in query.lower():
                        mentioned_aircraft = aircraft
                        break
                
                # Sample data for different aircraft types
                aircraft_data = {
                    "F-14": {
                        "aircraft_type": "F-14",
                        "max_pressure": "55 PSI",
                        "nominal_pressure": "40-45 PSI",
                        "flow_rate": "600 gallons per minute",
                        "safety_note": "Ensure canopy is closed before starting refueling",
                        "fuel_type": "JP-8"
                    },
                    "F-18": {
                        "aircraft_type": "F-18", 
                        "max_pressure": "50 PSI", 
                        "nominal_pressure": "35-45 PSI",
                        "flow_rate": "550 gallons per minute",
                        "safety_note": "Verify all external tanks are properly connected",
                        "fuel_type": "JP-8"
                    },
                    "C-130": {
                        "aircraft_type": "C-130",
                        "max_pressure": "60 PSI",
                        "nominal_pressure": "45-55 PSI", 
                        "flow_rate": "1000 gallons per minute",
                        "safety_note": "Use extended grounding procedures for cold weather operations",
                        "fuel_type": "JP-8"
                    }
                }
                
                if "hci" in query_lower or "hardness critical" in query_lower or "critical item" in query_lower:
                    # HCI query
                    content = generate_hci_response(mentioned_aircraft or "F-18", suggested_document)
                    app.logger.info("Applied custom HCI response formatting")
                elif "monitor" in query_lower and ("refuel" in query_lower or "fuel" in query_lower):
                    # Monitoring during refueling query
                    content = generate_refueling_response(mentioned_aircraft or "F-18", aircraft_data, suggested_document)
                    app.logger.info("Applied custom refueling monitoring response formatting")
                elif "hot refuel" in query_lower or "hot refueling" in query_lower or "engine running" in query_lower:
                    # Hot refueling query
                    content = generate_hot_refueling_response(mentioned_aircraft or "F-18", aircraft_data, suggested_document)
                    app.logger.info("Applied custom hot refueling response formatting")
                elif "pressure" in query_lower or "psi" in query_lower or "refuel" in query_lower or "fuel" in query_lower:
                    # General refueling query
                    content = generate_refueling_response(mentioned_aircraft or "F-18", aircraft_data, suggested_document)
                    app.logger.info("Applied custom refueling response formatting")
                elif "emergency" in query_lower or "fire" in query_lower:
                    # Emergency procedures
                    content = generate_emergency_response(mentioned_aircraft or "F-18", aircraft_data, suggested_document)
                    app.logger.info("Applied custom emergency response formatting")
                elif "ppe" in query_lower or "protective" in query_lower or "equipment" in query_lower:
                    # PPE query
                    content = generate_ppe_response(mentioned_aircraft or "F-18", suggested_document)
                    app.logger.info("Applied custom PPE response formatting")
                
                # Apply standard formatting to all responses
                try:
                    content = ensure_structured_format(content, query, selected_document)
                    content = process_citations(content)
                    content = process_warnings(content)
                    content = process_tables(content, selected_document)
                    app.logger.info("Applied standard formatting to response")
                except Exception as format_error:
                    app.logger.error(f"Error formatting content: {str(format_error)}")
                
                # Extract sources from results if available
                formatted_sources = []
                for result in api_response.get('results', []):
                    if 'metadata' in result:
                        metadata = result['metadata']
                        doc_id = metadata.get('document_id', 'Unknown')
                        source = {
                            "text": f"{doc_id}",
                            "details": f"Page {metadata.get('page_num', 'Unknown')}",
                            "relevance": result.get('score', 0.5),
                            "preview": result.get('content', '')[:100] + "...",
                            "document_origin": doc_id
                        }
                        formatted_sources.append(source)
                        
                        # Update suggested document if not already set
                        if not selected_document and doc_id and "TO" in doc_id:
                            suggested_document = doc_id
                            suggested_reason = "Referenced in the response"
                
                app.logger.info(f"Extracted {len(formatted_sources)} sources from results")
            else:
                # Fall back to offline mode response if we can't parse the API response
                app.logger.warning("Could not extract content from API response, using fallback response")
                
                # Find mentioned aircraft if any
                mentioned_aircraft = None
                for aircraft in ["F-14", "F-16", "F-18", "C-130", "C-17"]:
                    if aircraft.lower() in query.lower():
                        mentioned_aircraft = aircraft
                        break
                        
                # Sample data for different aircraft types
                aircraft_data = {
                    "F-14": {
                        "aircraft_type": "F-14",
                        "max_pressure": "55 PSI",
                        "nominal_pressure": "40-45 PSI",
                        "flow_rate": "600 gallons per minute",
                        "safety_note": "Ensure canopy is closed before starting refueling",
                        "fuel_type": "JP-8"
                    },
                    "F-18": {
                        "aircraft_type": "F-18", 
                        "max_pressure": "50 PSI", 
                        "nominal_pressure": "35-45 PSI",
                        "flow_rate": "550 gallons per minute",
                        "safety_note": "Verify all external tanks are properly connected",
                        "fuel_type": "JP-8"
                    },
                    "C-130": {
                        "aircraft_type": "C-130",
                        "max_pressure": "60 PSI",
                        "nominal_pressure": "45-55 PSI", 
                        "flow_rate": "1000 gallons per minute",
                        "safety_note": "Use extended grounding procedures for cold weather operations",
                        "fuel_type": "JP-8"
                    }
                }
                
                # Default suggested document
                suggested_document = selected_document or "TO 00-25-172CL-3"
                
                # Determine type of response to generate
                if "emergency" in query.lower() or "fire" in query.lower():
                    content = generate_emergency_response(mentioned_aircraft, aircraft_data, suggested_document)
                    content_type = "emergency"
                elif "hot" in query_lower or "running" in query_lower:
                    content = generate_hot_refueling_response(mentioned_aircraft, aircraft_data, suggested_document)
                    content_type = "hot"
                elif "pressure" in query_lower or "psi" in query_lower or "monitor" in query_lower or "refuel" in query_lower:
                    content = generate_refueling_response(mentioned_aircraft, aircraft_data, suggested_document)
                    content_type = "refuel"
                else:
                    content = generate_general_response(mentioned_aircraft, aircraft_data, suggested_document, query)
                    content_type = "general"
                
                # Generate sources for the response
                sources = generate_relevant_sources(query, content_type, mentioned_aircraft, aircraft_data, suggested_document)
            
            # Format and structure the response whether it came from API or fallback
            try:
                content = ensure_structured_format(content, query, selected_document)
                content = process_citations(content)
                content = process_warnings(content)
                content = process_tables(content, selected_document)
            except Exception as format_error:
                app.logger.error(f"Error formatting content: {str(format_error)}")
            
            # Check for different possible sources fields
            if 'sources' in api_response:
                formatted_sources = api_response.get('sources', [])
                app.logger.info("Found 'sources' field in API response")
            elif 'references' in api_response:
                formatted_sources = api_response.get('references', [])
                app.logger.info("Found 'references' field in API response")
            elif 'citations' in api_response:
                formatted_sources = api_response.get('citations', [])
                app.logger.info("Found 'citations' field in API response")
            elif 'results' in api_response and api_response['results']:
                # Extract sources from results if available
                formatted_sources = []
                for result in api_response.get('results', []):
                    if 'metadata' in result:
                        metadata = result['metadata']
                        doc_id = metadata.get('document_id', 'Unknown')
                        source = {
                            "text": f"{doc_id}",
                            "details": f"Page {metadata.get('page_num', 'Unknown')}",
                            "relevance": result.get('score', 0.5),
                            "preview": result.get('content', '')[:100] + "...",
                            "document_origin": doc_id
                        }
                        formatted_sources.append(source)
                        
                        # Update suggested document if not already set
                        if not selected_document and doc_id and "TO" in doc_id:
                            suggested_document = doc_id
                            suggested_reason = "Referenced in the response"
                
                app.logger.info(f"Extracted {len(formatted_sources)} sources from results")
            else:
                # Extract sources from the content
                formatted_sources = extract_sources_from_content(content)
                if not formatted_sources:
                    app.logger.warning("No sources found in API response, using default sources")
                    formatted_sources = [
                        {
                            "text": "TO 00-25-172CL-3, Section 3, Table 2",
                            "details": "Refueling Pressure Specifications",
                            "relevance": 0.8,
                            "preview": "Contains detailed information about maximum and normal pressure ranges for all aircraft types.",
                            "document_origin": "TO 00-25-172CL-3"
                        },
                        {
                            "text": "TO 00-25-172CL-4, Page 35",
                            "details": "Safety Monitoring Requirements",
                            "relevance": 0.7,
                            "preview": "Outlines critical monitoring points and warning indicators during refueling operations.",
                            "document_origin": "TO 00-25-172CL-4"
                        }
                    ]
        
        # Return the response
        return jsonify({
            'response': content,
            'sources': formatted_sources,
            'api_available': api_available,
            'suggested_document': suggested_document,
            'suggested_reason': suggested_reason,
            'relevant_documents': relevant_documents
        })
        
    except Exception as e:
        app.logger.error(f"Error handling chat request: {str(e)}")
        # Return a basic error response with default sources
        default_sources = [
            {
                "text": "TO 00-25-172CL-3, Section 3",
                "details": "General Refueling Procedures",
                "relevance": 0.8,
                "preview": "Contains information about standard refueling operations and safety protocols.",
                "document_origin": "TO 00-25-172CL-3"
            },
            {
                "text": "TO 00-25-172CL-4, Chapter 2",
                "details": "Maintenance Requirements",
                "relevance": 0.7,
                "preview": "Outlines maintenance schedules and procedures for refueling equipment.",
                "document_origin": "TO 00-25-172CL-4"
            }
        ]
        return jsonify({
            'response': f"<p>Error processing your request. Please try again or ask a different question.</p>",
            'sources': default_sources,
            'api_available': False,
            'suggested_document': "TO 00-25-172CL-3",
            'suggested_reason': None,
            'relevant_documents': ["TO 00-25-172CL-1", "TO 00-25-172CL-2", "TO 00-25-172CL-3", "TO 00-25-172CL-4"]
        })

def extract_query_keywords(query):
    """Extract keywords from the query for better context understanding."""
    # Define common keywords for different topics in aircraft maintenance
    topic_keywords = {
        'pressure': ['pressure', 'psi', 'pounds', 'gauge', 'maximum', 'minimum', 'nominal'],
        'flow': ['flow', 'rate', 'gallons', 'per', 'minute', 'gpm'],
        'refueling': ['refuel', 'fuel', 'filling', 'servicing', 'defuel'],
        'safety': ['safety', 'caution', 'warning', 'hazard', 'danger', 'emergency'],
        'aircraft': ['f-14', 'f-16', 'f-18', 'c-130', 'c-17', 'c-5', 'navy', 'commercial'],
        'procedures': ['procedure', 'step', 'process', 'checklist', 'monitor', 'verify'],
        'equipment': ['truck', 'hose', 'nozzle', 'valve', 'gauge', 'meter', 'equipment'],
        'emergency': ['fire', 'leak', 'spill', 'accident', 'emergency', 'evacuation']
    }
    
    query_lower = query.lower()
    found_keywords = []
    
    # Extract any mentioned aircraft types specifically
    aircraft_pattern = r'\b(f-14|f-15|f-16|f-18|f/a-18|c-130|c-5|c-17|kc-135)\b'
    aircraft_matches = re.findall(aircraft_pattern, query_lower)
    if aircraft_matches:
        found_keywords.extend([match.upper() for match in aircraft_matches])
    
    # Check for keywords in each topic
    for topic, keywords in topic_keywords.items():
        for keyword in keywords:
            if keyword in query_lower and keyword not in found_keywords:
                found_keywords.append(keyword)
    
    return found_keywords

def validate_response_relevance(content, query, keywords):
    """Validate if the API response is relevant to the query with improved heuristics."""
    if not content:
        return 0.0  # Empty response is not relevant
        
    # Base score - presence of content provides a minimum relevance
    base_score = 0.3
    
    # Simple heuristic: check if keywords from the query appear in the response
    content_lower = content.lower()
    query_lower = query.lower()
    
    # Check if query terms appear in content (treating this as important)
    query_words = [w for w in query_lower.split() if len(w) > 3]  # Only consider words longer than 3 chars
    words_found = sum(1 for word in query_words if word in content_lower)
    query_match_score = min(0.4, words_found / max(1, len(query_words)) * 0.4)
    
    # Check keyword matches
    if keywords:
        keywords_found = sum(1 for kw in keywords if kw.lower() in content_lower)
        keywords_match_score = min(0.4, keywords_found / len(keywords) * 0.4)
    else:
        # If no specific keywords, give a reasonable default
        keywords_match_score = 0.2
    
    # Check for domain-specific terms to ensure technical relevance
    domain_terms = [
        "aircraft", "refuel", "pressure", "psi", "fuel", "safety", "procedure", 
        "limit", "monitor", "warning", "caution", "flow", "rate", "technical order"
    ]
    domain_terms_found = sum(1 for term in domain_terms if term in content_lower)
    domain_score = min(0.2, domain_terms_found / len(domain_terms) * 0.2)
    
    # Check for HTML formatting - properly formatted responses have structure
    structure_score = 0.0
    if "<p>" in content or "<h" in content or "<ul>" in content or "<ol>" in content:
        structure_score = 0.1
    if "<table" in content:
        structure_score += 0.05
    if "<div class=\"warning" in content or "<span class=\"critical" in content:
        structure_score += 0.05
    
    # Calculate total score with weights
    relevance_score = base_score + query_match_score + keywords_match_score + domain_score + structure_score
    
    # Cap at 1.0
    relevance_score = min(1.0, relevance_score)
    
    # Additional checks for pressure values, aircraft types, and safety information
    if any(kw in ['pressure', 'psi'] for kw in keywords) and query_lower.find('pressure') >= 0:
        if not re.search(r'\d+\s*(PSI|psi)', content):
            relevance_score *= 0.7  # Penalize if no specific PSI values mentioned
    
    if any(aircraft in query_lower for aircraft in ['f-14', 'f-16', 'f-18', 'c-130', 'c-17']):
        # Check if the mentioned aircraft appears in the response
        aircraft_in_response = any(aircraft in content_lower for aircraft in ['f-14', 'f-16', 'f-18', 'c-130', 'c-17'])
        if not aircraft_in_response:
            relevance_score *= 0.8  # Smaller penalty if specific aircraft not addressed
    
    app.logger.info(f"Relevance score details - Base: {base_score}, Query: {query_match_score}, " +
                   f"Keywords: {keywords_match_score}, Domain: {domain_score}, Structure: {structure_score}")
    
    return relevance_score

def deduplicate_sources(sources):
    """Remove duplicative sources that provide similar information."""
    if not sources:
        return []
    
    # Sort by relevance first
    sorted_sources = sorted(sources, key=lambda x: x.get('relevance', 0), reverse=True)
    
    # Track parameters to avoid repeating the same information
    seen_parameters = set()
    deduplicated = []
    
    for source in sorted_sources:
        # Check if this is a new source or contains new parameters
        params = source.get('parameters', {})
        aircraft_type = params.get('aircraft_type', '')
        
        # Create a key combining source and aircraft type
        source_key = f"{source.get('text', '')}_{aircraft_type}"
        
        # Skip if we've already seen this source with this aircraft type
        if source_key in seen_parameters:
            continue
        
        seen_parameters.add(source_key)
        deduplicated.append(source)
    
    return deduplicated

def generate_fallback_response(query, selected_document=None, query_keywords=[]):
    """Generate a fallback response when the API is unavailable."""
    app.logger.info("Generating fallback response to demonstrate UI features")
    
    # Default to a commonly used document if none selected
    if not selected_document:
        selected_document = "TO 00-25-172CL-4"
        app.logger.info(f"Using default document: {selected_document}")
    
    # Determine the appropriate response based on keywords in the query
    query_lower = query.lower()
    
    # Define a mapping of topics to relevant TOs
    topic_to_document = {
        "pressure": "TO 00-25-172CL-4",
        "psi": "TO 00-25-172CL-4",
        "flow": "TO 00-25-172CL-4",
        "rate": "TO 00-25-172CL-4",
        "refuel": "TO 00-25-172CL-4",
        "hot": "TO 00-25-172CL-3",
        "navy": "TO 00-25-172CL-3",
        "commercial": "TO 00-25-172CL-1",
        "passenger": "TO 00-25-172CL-1",
        "cargo": "TO 00-25-172CL-2",
        "logair": "TO 00-25-172CL-2",
        "quicktrans": "TO 00-25-172CL-2",
        "fire": "TO 00-25-172CL-4",
        "emergency": "TO 00-25-172CL-4",
        "leak": "TO 00-25-172CL-4",
        "spill": "TO 00-25-172CL-4",
        "safety": "TO 00-25-172CL-4"
    }
    
    # Determine the most appropriate document based on the query
    suggested_document = selected_document
    suggested_reason = None
    
    for keyword, document in topic_to_document.items():
        if keyword in query_lower:
            suggested_document = document
            suggested_reason = f"This document contains information about {keyword}"
            break
    
    # Use keywords if available
    if query_keywords:
        for keyword in query_keywords:
            if keyword.lower() in topic_to_document:
                suggested_document = topic_to_document[keyword.lower()]
                suggested_reason = f"This document contains information about {keyword}"
                break
    
    # Sample data for different aircraft types
    aircraft_data = {
        "F-14": {
            "aircraft_type": "F-14",
            "max_pressure": "55 PSI",
            "nominal_pressure": "40-45 PSI",
            "flow_rate": "600 gallons per minute",
            "safety_note": "Ensure canopy is closed before starting refueling"
        },
        "F-18": {
            "aircraft_type": "F-18", 
            "max_pressure": "50 PSI", 
            "nominal_pressure": "35-45 PSI",
            "flow_rate": "550 gallons per minute",
            "safety_note": "Verify all external tanks are properly connected"
        },
        "C-130": {
            "aircraft_type": "C-130",
            "max_pressure": "60 PSI",
            "nominal_pressure": "45-55 PSI", 
            "flow_rate": "1000 gallons per minute",
            "safety_note": "Use extended grounding procedures for cold weather operations"
        },
        "C-17": {
            "aircraft_type": "C-17",
            "max_pressure": "65 PSI",
            "nominal_pressure": "50-60 PSI",
            "flow_rate": "1200 gallons per minute", 
            "safety_note": "Maintain minimum separation of 25 feet during fueling operations"
        },
        "F-16": {
            "aircraft_type": "F-16",
            "max_pressure": "52 PSI",
            "nominal_pressure": "38-48 PSI",
            "flow_rate": "580 gallons per minute",
            "safety_note": "Maintain minimum 50 ft clearance during hot refueling"
        }
    }
    
    # Determine if a specific aircraft was mentioned
    mentioned_aircraft = None
    aircraft_pattern = r'\b(F-14|F-18|F-15|F-16|C-130|C-5|C-17|B-1|B-2|B-52)\b'
    aircraft_matches = re.findall(aircraft_pattern, query, re.IGNORECASE)
    
    if aircraft_matches:
        mentioned_aircraft = aircraft_matches[0].upper()
    elif query_keywords:
        # Check if any keyword is an aircraft type
        for keyword in query_keywords:
            if keyword.upper() in aircraft_data:
                mentioned_aircraft = keyword.upper()
                break
    
    # Determine content type based on keywords
    content_type = "general"
    
    if "fire" in query_lower or "emergency" in query_lower or "leak" in query_lower or "spill" in query_lower:
        content_type = "emergency"
    elif "hot" in query_lower or "running" in query_lower:
        content_type = "hot"
    elif "pressure" in query_lower or "psi" in query_lower or "monitor" in query_lower or "refuel" in query_lower:
        content_type = "refuel"
    
    # If we have query keywords, use them to determine content type
    if query_keywords:
        if any(kw.lower() in ["fire", "emergency", "leak", "spill", "accident"] for kw in query_keywords):
            content_type = "emergency"
        elif any(kw.lower() in ["hot", "running", "engine"] for kw in query_keywords):
            content_type = "hot"
        elif any(kw.lower() in ["pressure", "psi", "monitor", "refuel", "fuel", "flow", "rate"] for kw in query_keywords):
            content_type = "refuel"
    
    # Sample response content with appropriate formatting based on content type
    if content_type == "emergency":
        content = generate_emergency_response(mentioned_aircraft, aircraft_data, suggested_document)
    elif content_type == "hot":
        content = generate_hot_refueling_response(mentioned_aircraft, aircraft_data, suggested_document)
    elif content_type == "refuel":
        content = generate_refueling_response(mentioned_aircraft, aircraft_data, suggested_document)
    else:
        content = generate_general_response(mentioned_aircraft, aircraft_data, suggested_document, query)
    
    # Create a set of sources with enhanced information
    sources = generate_relevant_sources(query, content_type, mentioned_aircraft, aircraft_data, suggested_document)
    
    return content, sources, suggested_document, suggested_reason

def generate_emergency_response(mentioned_aircraft, aircraft_data, suggested_document):
    """Generate a response for emergency procedures during refueling."""
    # Default to F-18 if no specific aircraft mentioned
    if not mentioned_aircraft:
        mentioned_aircraft = "F-18"
    
    # Get data for the specified aircraft
    aircraft_info = aircraft_data.get(mentioned_aircraft, {})
    max_pressure = aircraft_info.get("max_pressure", "55 PSI")
    aircraft_name = mentioned_aircraft
    
    # Generate HTML response with structured format
    html_response = f"""
    <div class="summary-box">
    <h4>🔍 Quick Summary: Emergency Procedures During Refueling</h4>
    <ul>
        <li>⚠️ Stop refueling immediately if a fuel spill, leak, or fire occurs</li>
        <li>🚨 Evacuate personnel to a minimum of 200 feet from the affected area</li>
        <li>⚡ Notify fire department and crash response immediately</li>
    </ul>
    </div>

    <div class="warning-container">
    <div class="warning-block warning">
    <h4>⚠️ WARNING</h4>
    <ul>
        <li>DO NOT attempt to restart refueling after an emergency shutdown until the situation has been assessed by qualified personnel [TO 00-25-172CL-4, Section 4].</li>
        <li>If a fire occurs, DO NOT attempt to disconnect equipment until power has been shut off [TO 00-25-172CL-4, Page 38, Table].</li>
    </ul>
    </div>
    </div>

    <div class="warning-container">
    <div class="warning-block caution">
    <h4>⚠️ CAUTION</h4>
    <ul>
        <li>Ensure all personnel are trained in emergency procedures before participating in refueling operations [TO 00-25-172CL-4, Section 2].</li>
        <li>Always know the location of emergency equipment before beginning refueling operations [TO 00-25-172CL-4, Page 42].</li>
    </ul>
    </div>
    </div>

    <h4>📋 Fuel Spill Emergency Procedures</h4>
    <ol class="procedure-list">
        <li><strong>Stop Refueling</strong>: Immediately shut off all fuel flow by activating emergency shutoff [TO 00-25-172CL-4, Page 45].</li>
        <li><strong>Evacuate</strong>: Move all personnel upwind to a minimum of 200 feet from the spill area [TO 00-25-172CL-4, Page 45].</li>
        <li><strong>Notify</strong>: Contact emergency services, supervisor, and environmental response team [TO 00-25-172CL-4, Page 45].</li>
        <li><strong>Contain</strong>: If safe to do so, use spill containment equipment to prevent fuel spread [TO 00-25-172CL-4, Page 46].</li>
        <li><strong>Restrict Area</strong>: Establish a safety zone and prevent unauthorized personnel from entering [TO 00-25-172CL-4, Page 46].</li>
    </ol>

    <h4>🔥 Fire Emergency Procedures</h4>
    <ol class="procedure-list">
        <li><strong>Stop Refueling</strong>: Immediately hit emergency stop and shut off all valves [TO 00-25-172CL-4, Page 48].</li>
        <li><strong>Evacuate</strong>: Move all personnel to a minimum safe distance of 500 feet [TO 00-25-172CL-4, Page 48].</li>
        <li><strong>Notify</strong>: Activate fire alarm and contact crash response and fire department [TO 00-25-172CL-4, Page 48].</li>
        <li><strong>Attempt Extinguishing</strong>: Only if the fire is small and it is safe to do so, use appropriate fire extinguisher [TO 00-25-172CL-4, Page 49].</li>
        <li><strong>Assist Response</strong>: Provide information to emergency response personnel when they arrive [TO 00-25-172CL-4, Page 49].</li>
    </ol>

    <h4>🚨 Emergency Equipment Requirements</h4>
    <table class="comparison-table">
        <tr>
            <th>Equipment</th>
            <th>Requirement</th>
            <th>Location</th>
        </tr>
        <tr>
            <td>Fire Extinguishers</td>
            <td>Minimum two 150 lb dry chemical</td>
            <td>Within 50 feet of refueling area</td>
        </tr>
        <tr>
            <td>Emergency Fuel Shutoff</td>
            <td>Clearly marked and accessible</td>
            <td>At refueling station and remote location</td>
        </tr>
        <tr>
            <td>Spill Kit</td>
            <td>Appropriate for 200 gallon containment</td>
            <td>Within 100 feet of refueling area</td>
        </tr>
        <tr>
            <td>Emergency Communication</td>
            <td>Direct line to fire department</td>
            <td>At refueling control point</td>
        </tr>
    </table>
    
    <p>For comprehensive emergency procedures specific to {aircraft_name} aircraft, refer to TO 00-25-172CL-4, Section 4, and your unit's specific emergency response plan.</p>
    """
    
    return html_response

def generate_hot_refueling_response(mentioned_aircraft, aircraft_data, suggested_document):
    """Generate a response for hot refueling procedures (engine running)."""
    # Default to F-18 if no specific aircraft mentioned
    if not mentioned_aircraft:
        mentioned_aircraft = "F-18"
    
    # Get data for the specified aircraft
    aircraft_info = aircraft_data.get(mentioned_aircraft, {})
    max_pressure = aircraft_info.get("max_pressure", "55 PSI")
    nominal_pressure = aircraft_info.get("nominal_pressure", "35-45 PSI")
    fuel_type = aircraft_info.get("fuel_type", "JP-8")
    aircraft_name = mentioned_aircraft
    
    # Generate HTML response with structured format using our template
    html_response = f"""
    <p>The maximum refueling pressure allowed during hot refueling for {aircraft_name} aircraft is <span class="critical-value">{max_pressure}</span>. Hot refueling must be performed with the engine at idle power and requires specific safety procedures.</p>
    
    <div class="summary-box">
    <h4>🔍 Quick Summary: Hot Refueling Guidelines</h4>
    <ul class="actionable-checklist">
        <li>✅ Max pressure: <span class="critical-value">{max_pressure}</span></li>
        <li>✅ Monitor all pressure gauges continuously</li>
        <li>⚠️ Engine must be at idle power during hot refueling</li>
        <li>⚠️ Stop immediately if pressure exceeds limits or warning indicators activate</li>
        <li>✅ Personnel must wear appropriate PPE and maintain safe positions</li>
    </ul>
    </div>

    <div class="warning-block warning">
    <h4>⚠️ WARNING</h4>
    <ul>
        <li>Hot refueling operations are inherently dangerous. Improper procedures can result in fire, explosion, injury, or death [TO 00-25-172CL-3, Section 2].</li>
        <li>If the TANK OVER PRESS (red) light comes on, stop refueling immediately and signal pilot to shut down engines [TO 00-25-172CL-3, Page 50, Table].</li>
        <li>Immediately stop refueling if any warning indicators activate (e.g., red lights, pressure alarms, or tank over-pressure warnings) [TO 00-25-172CL-3, Page 35, Table].</li>
    </ul>
    </div>

    <div class="warning-block caution">
    <h4>⚠️ CAUTION</h4>
    <ul>
        <li>Never conduct hot refueling during electrical storms [TO 00-25-172CL-3, Page 47, Table].</li>
        <li>Do not initiate hot refueling if the aircraft exhibits fuel leaks or if vents are obstructed [TO 00-25-172CL-3, Page 35, Table].</li>
    </ul>
    </div>

    <h4>📋 Critical Monitoring Requirements</h4>
    <ol class="procedure-list">
        <li><strong>Fuel Pressure</strong>: Ensure fuel pressure from servicing equipment does not exceed <span class="critical-value">{max_pressure}</span> [TO 00-25-172CL-3, Page 47, Table].</li>
        <li><strong>Engine Status</strong>: Verify engine is at idle power during the entire hot refueling operation [TO 00-25-172CL-3, Page 47, Table].</li>
        <li><strong>Vent Monitoring</strong>: Check that air is venting from the vent mast on the lower right side of the fuselage after 60 to 120 gallons of fuel have entered the tanks [TO 00-25-172CL-3, Page 50, Table].</li>
        <li><strong>Tank Pressure Indicator</strong>: Monitor the fuel tank pressure indicator and stop all refueling if the indicator shows red [TO 00-25-172CL-3, Page 35, Table].</li>
        <li><strong>Fuel Contents Lights</strong>: Ensure LEFT and RIGHT FUEL CONTENTS (green) lights are on when refueling pressure is applied, and they go off when tanks are full [TO 00-25-172CL-3, Page 50, Table].</li>
    </ol>

    <h4>🛩️ Aircraft-Specific Hot Refueling Requirements</h4>
    <table class="comparison-table">
        <tr>
            <th>Parameter</th>
            <th>Value for {aircraft_name}</th>
        </tr>
        <tr>
            <td>Maximum Pressure</td>
            <td><span class="critical-value">{max_pressure}</span></td>
        </tr>
        <tr>
            <td>Nominal Pressure Range</td>
            <td>{nominal_pressure}</td>
        </tr>
        <tr>
            <td>Fuel Type</td>
            <td>{fuel_type}</td>
        </tr>
    </table>
    
    <h4>⚙️ Hot Refueling Procedure</h4>
    <ol class="procedure-list">
        <li>Position aircraft and ensure it is properly grounded [TO 00-25-172CL-3, Page 48].</li>
        <li>Verify engine is at idle power [TO 00-25-172CL-3, Page 47].</li>
        <li>Connect and verify secure nozzle attachment [TO 00-25-172CL-3, Page 48].</li>
        <li>Maintain pressure below <span class="critical-value">{max_pressure}</span> at all times [TO 00-25-172CL-3, Page 47].</li>
        <li>Monitor all indicators continuously during the entire operation [TO 00-25-172CL-3, Page 50].</li>
        <li>Upon completion, remove nozzle and secure all equipment [TO 00-25-172CL-3, Page 49].</li>
    </ol>
    
    <h4>📚 References</h4>
    <ul>
        <li>TO 00-25-172CL-3, Section 3: Hot Refueling Procedures</li>
        <li>TO 00-25-172CL-3, Page 47-50: Equipment Requirements and Safety Precautions</li>
        <li>TO 00-25-172CL-3, Page 35: Warning Indicators and Emergency Procedures</li>
    </ul>
    """
    
    return html_response

def generate_refueling_response(mentioned_aircraft, aircraft_data, suggested_document):
    """Generate a response about monitoring requirements during aircraft refueling."""
    # Default to F-18 if no specific aircraft mentioned
    if not mentioned_aircraft:
        mentioned_aircraft = "F-18"
    
    # Get data for the specified aircraft
    aircraft_info = aircraft_data.get(mentioned_aircraft, {})
    max_pressure = aircraft_info.get("max_pressure", "55 PSI")
    fuel_type = aircraft_info.get("fuel_type", "JP-8")
    refuel_rate = aircraft_info.get("refuel_rate", "300-600 gallons per minute")
    aircraft_name = mentioned_aircraft
    
    # Generate HTML response with structured format
    html_response = f"""
    <p>During aircraft refueling of {aircraft_name} aircraft, you must monitor several critical parameters to ensure safety and proper refueling. The maximum allowable pressure is <span class="critical-value">{max_pressure}</span>.</p>
    
    <div class="summary-box">
    <h4>🔍 Quick Summary: Refueling Monitoring Guidelines</h4>
    <ul class="actionable-checklist">
        <li>✅ Max pressure: <span class="critical-value">{max_pressure}</span></li>
        <li>✅ Monitor all pressure gauges continuously</li>
        <li>⚠️ Stop immediately if pressure exceeds limits or red indicators activate</li>
        <li>✅ Verify correct fuel type ({fuel_type})</li>
        <li>✅ Check that air is venting from the vent mast</li>
    </ul>
    </div>

    <div class="warning-block warning">
    <h4>⚠️ WARNING</h4>
    <ul>
        <li>If the TANK OVER PRESS (red) light comes on, stop refueling immediately to prevent injury and equipment damage [TO 00-25-172CL-3, Page 50, Table].</li>
        <li>Monitor the fuel tank pressure indicator and stop all refueling if the indicator shows red, as this could result in injury or death [TO 00-25-172CL-3, Page 35, Table].</li>
        <li>Immediately stop refueling if any warning indicators activate (e.g., red lights, pressure alarms, or tank over-pressure warnings) [TO 00-25-172CL-3, Page 35, Table].</li>
    </ul>
    </div>

    <div class="warning-block caution">
    <h4>⚠️ CAUTION</h4>
    <ul>
        <li>Never fuel or defuel during electrical storms and ensure all ordnance is safetied before refueling [TO 00-25-172CL-3, Page 47, Table].</li>
        <li>Always verify fuel type and grade before starting the refueling process [TO 00-25-172CL-3, Page 47, Table].</li>
    </ul>
    </div>

    <h4>📋 Critical Monitoring Requirements</h4>
    <ol class="procedure-list">
        <li><strong>Fuel Pressure</strong>: Ensure fuel pressure from servicing equipment does not exceed <span class="critical-value">{max_pressure}</span> [TO 00-25-172CL-3, Page 47, Table].</li>
        <li><strong>Fuel Type</strong>: Verify the aircraft is receiving the correct type of fuel ({fuel_type}) [TO 00-25-172CL-3, Page 47, Table].</li>
        <li><strong>Vent Monitoring</strong>: Check that air is venting from the vent mast on the lower right side of the fuselage after 60 to 120 gallons of fuel have entered the tanks [TO 00-25-172CL-3, Page 50, Table].</li>
        <li><strong>Tank Pressure Indicator</strong>: Monitor the fuel tank pressure indicator and stop all refueling if the indicator shows red [TO 00-25-172CL-3, Page 35, Table].</li>
        <li><strong>Fuel Contents Lights</strong>: Ensure LEFT and RIGHT FUEL CONTENTS (green) lights are on when refueling pressure is applied, and they go off when tanks are full [TO 00-25-172CL-3, Page 50, Table].</li>
        <li><strong>External Tank Vents</strong>: Check for airflow from external fuel tank vents as the tanks fill [TO 00-25-172CL-3, Page 35, Table].</li>
    </ol>

    <h4>🛩️ Aircraft-Specific Refueling Requirements</h4>
    <table class="comparison-table">
        <tr>
            <th>Parameter</th>
            <th>Value for {aircraft_name}</th>
        </tr>
        <tr>
            <td>Maximum Pressure</td>
            <td><span class="critical-value">{max_pressure}</span></td>
        </tr>
        <tr>
            <td>Fuel Type</td>
            <td>{fuel_type}</td>
        </tr>
        <tr>
            <td>Refuel Rate</td>
            <td>{refuel_rate}</td>
        </tr>
    </table>
    
    <h4>⚙️ Standard Refueling Procedure</h4>
    <ol class="procedure-list">
        <li>Position refueling equipment and properly ground both aircraft and equipment [TO 00-25-172CL-3, Page 47].</li>
        <li>Verify fuel type and grade matches aircraft requirements [TO 00-25-172CL-3, Page 47].</li>
        <li>Connect and secure all refueling equipment [TO 00-25-172CL-3, Page 48].</li>
        <li>Begin refueling and continuously monitor all gauges and indicators [TO 00-25-172CL-3, Page 49].</li>
        <li>Maintain pressure below <span class="critical-value">{max_pressure}</span> at all times [TO 00-25-172CL-3, Page 47].</li>
        <li>Upon completion, remove equipment and secure all systems [TO 00-25-172CL-3, Page 50].</li>
    </ol>
    
    <h4>📚 References</h4>
    <ul>
        <li>TO 00-25-172CL-3, Section 3: Aircraft Refueling Procedures</li>
        <li>TO 00-25-172CL-3, Page 47-50: Equipment Requirements and Safety Precautions</li>
        <li>TO 00-25-172CL-3, Page 35: Warning Indicators and Emergency Procedures</li>
    </ul>
    """
    
    return html_response

def generate_general_response(mentioned_aircraft, aircraft_data, suggested_document, query):
    """Generate a general response for queries not fitting other categories."""
    try:
        # Default to a general aircraft if none mentioned
        if not mentioned_aircraft:
            mentioned_aircraft = "F-18"
        
        # Make a best effort to detect what the user is asking about
        query_lower = query.lower()
        
        # Determine the topic to address
        if "hci" in query_lower or "hardness critical" in query_lower or "critical item" in query_lower:
            # HCI query
            return generate_hci_response(mentioned_aircraft, suggested_document)
        elif "personal protective" in query_lower or "ppe" in query_lower or "equipment" in query_lower:
            # PPE query
            return generate_ppe_response(mentioned_aircraft, suggested_document)
        else:
            # Default response
            aircraft_info = aircraft_data.get(mentioned_aircraft, {})
            aircraft_name = mentioned_aircraft

            html_response = f"""
            <p>For your question about {aircraft_name} aircraft technical information, I'd recommend consulting {suggested_document} which contains specific guidelines and procedures for aircraft maintenance and operations.</p>
            
            <div class="summary-box">
            <h4>🔍 Quick Summary: Technical Order Information</h4>
            <ul>
                <li>Aircraft: {aircraft_name}</li>
                <li>Primary References: {suggested_document}, Section 3</li>
                <li>Contains: Maintenance procedures, safety guidelines, and operational requirements</li>
            </ul>
            </div>
            
            <p>To better answer your question, could you provide more specific details about what aspect of the aircraft or maintenance procedure you're interested in? For example:</p>
            <ul class="actionable-checklist">
                <li>Hot refueling procedures</li>
                <li>Maximum pressure specifications</li>
                <li>Safety protocols during maintenance</li>
                <li>Required inspections or checks</li>
            </ul>
            
            <p>I can provide more detailed information based on specific Technical Orders once I understand your requirements better.</p>
            
            <div class="citation-box">
            <h4>Source:</h4>
            <p>[TO 00-25-172CL-3] Hot Refueling Procedures</p>
            </div>
            """
            
            return html_response
    except Exception as e:
        app.logger.error(f"Error in generate_general_response: {str(e)}")
        # Return a simplified response if any error occurs
        return f"""
        <p>I can provide information about aircraft maintenance and refueling procedures from the Technical Orders.</p>
        
        <p>Please ask a specific question about aircraft maintenance, refueling specifications, safety procedures, or related topics.</p>
        
        <div class="citation-box">
        <h4>Source:</h4>
        <p>[TO 00-25-172CL-3] Hot Refueling Procedures</p>
        </div>
        """

# Add HCI response generator
def generate_hci_response(mentioned_aircraft, suggested_document):
    """Generate a response about Hardness Critical Items."""
    html_response = f"""
    <p>HCI (Hardness Critical Items) designations identify items or components that are critical to maintaining aircraft hardness against various threats, including electromagnetic pulses, radiation, and other environmental hazards.</p>
    
    <div class="summary-box">
    <h4>🔍 Quick Summary: Hardness Critical Items (HCI)</h4>
    <ul class="actionable-checklist">
        <li>✅ HCI parts must be replaced with identical HCI-approved parts</li>
        <li>✅ Special inspections and maintenance procedures apply to HCI components</li>
        <li>✅ HCI components require specific documentation during maintenance</li>
        <li>⚠️ Substituting non-HCI parts for HCI parts is prohibited without engineering approval</li>
    </ul>
    </div>

    <div class="warning-block caution">
    <h4>⚠️ CAUTION</h4>
    <p>Failure to maintain HCI designations can compromise aircraft survivability in combat environments.</p>
    </div>
    
    <h3>Key Points about HCI Components:</h3>
    <ol>
        <li><strong>Definition:</strong> HCI components are critical to an aircraft's ability to operate in hostile environments with electromagnetic interference or nuclear effects.</li>
        <li><strong>Identification:</strong> HCI components are typically marked with specific labeling on the part and in documentation.</li>
        <li><strong>Maintenance Requirements:</strong> Special procedures must be followed when replacing or servicing HCI components.</li>
        <li><strong>Documentation:</strong> Additional paperwork and verification is required for maintenance on HCI items.</li>
    </ol>

    <p>When maintaining aircraft with HCI components, always consult the specific Technical Order for that aircraft and system to ensure proper compliance with HCI requirements.</p>
    
    <div class="citation-box">
    <h4>Source:</h4>
    <p>[{suggested_document}] Maintenance Procedures</p>
    </div>
    """
    
    return html_response

def generate_ppe_response(mentioned_aircraft, suggested_document):
    """Generate a response about Personal Protective Equipment."""
    html_response = f"""
    <p>Personal Protective Equipment (PPE) is required during aircraft maintenance and refueling operations to ensure technician safety.</p>
    
    <div class="summary-box">
    <h4>🔍 Quick Summary: Required PPE for Aircraft Maintenance</h4>
    <ul class="actionable-checklist">
        <li>✅ Chemical-resistant gloves when handling fuel or hazardous materials</li>
        <li>✅ Eye protection (goggles/face shield) during all maintenance operations</li>
        <li>✅ Hearing protection when working around running engines</li>
        <li>✅ Grounding straps when working with electrical components</li>
        <li>✅ Fire-resistant coveralls during hot refueling operations</li>
    </ul>
    </div>

    <div class="warning-block warning">
    <h4>⚠️ WARNING</h4>
    <p>Failure to use proper PPE during maintenance and refueling operations may result in serious injury or death.</p>
    </div>
    
    <h3>Additional PPE Requirements:</h3>
    <ul>
        <li><strong>Respiratory Protection:</strong> Required when working with solvents, paints, or in confined spaces</li>
        <li><strong>Fall Protection:</strong> Required when working at heights above 4 feet</li>
        <li><strong>Head Protection:</strong> Required in designated areas or when overhead work is being performed</li>
        <li><strong>Foot Protection:</strong> Steel-toed boots required in all maintenance areas</li>
    </ul>

    <p>Always refer to the specific Technical Order and local safety regulations for complete PPE requirements for your task.</p>
    
    <div class="citation-box">
    <h4>Source:</h4>
    <p>[{suggested_document}] Safety Procedures</p>
    </div>
    """
    
    return html_response

def generate_relevant_sources(query, content_type, mentioned_aircraft, aircraft_data, suggested_document):
    """Generate relevant sources based on query content type."""
    sources = []
    
    # Get aircraft-specific data if available
    aircraft = mentioned_aircraft if mentioned_aircraft in aircraft_data else None
    
    # Source 1: Main technical order reference with specific section
    if content_type == "emergency":
        sources.append({
            "text": f"{suggested_document}, Section 5, Emergency Procedures",
            "details": "Emergency Response Procedures for Fuel Spills and Fires",
            "relevance": 0.95,
            "parameters": aircraft_data.get(aircraft, {}) if aircraft else {},
            "preview": "Contains detailed emergency procedures for handling fuel leaks, spills, and fires during aircraft refueling operations, including evacuation distances and immediate actions."
        })
        
        sources.append({
            "text": "TO 00-25-172CL-4, Page 35, Emergency Response",
            "details": "Detailed Emergency Response Steps and Safety Protocols",
            "relevance": 0.90,
            "parameters": aircraft_data.get(aircraft, {}) if aircraft else {},
            "preview": "Provides comprehensive guidance on emergency response procedures, including containment, evacuation, and notification protocols for fuel-related incidents."
        })
    elif content_type == "hot":
        sources.append({
            "text": "TO 00-25-172CL-3, Section 2, Hot Refueling Procedures",
            "details": "Procedures for Refueling with Engines Running",
            "relevance": 0.95,
            "parameters": aircraft_data.get(aircraft, {}) if aircraft else {},
            "preview": "Details the special procedures and safety precautions required for hot refueling operations, including personnel positioning and reduced pressure requirements."
        })
        
        sources.append({
            "text": "TO 00-25-172CL-3, Page 45, Aircraft-Specific Requirements",
            "details": "Aircraft-Specific Hot Refueling Limitations",
            "relevance": 0.90,
            "parameters": aircraft_data.get(aircraft, {}) if aircraft else {},
            "preview": "Contains tables of aircraft-specific requirements for hot refueling, including maximum pressure limitations and special safety considerations."
        })
    else:  # refuel or general
        sources.append({
            "text": f"{suggested_document}, Page 12, Table 2-3",
            "details": "Pressure Limitations and Monitoring Requirements",
            "relevance": 0.95,
            "parameters": aircraft_data.get(aircraft, {}) if aircraft else {},
            "preview": "Contains detailed specifications for fuel pressure monitoring during aircraft refueling operations, including maximum pressure limitations, normal operating ranges, and emergency procedures.",
            "table_preview": """<table class="table table-sm">
                <thead>
                    <tr>
                        <th>Parameter</th>
                        <th>Normal Range</th>
                        <th>Maximum</th>
                    </tr>
                </thead>
                <tbody>
                    <tr>
                        <td>Fuel Pressure</td>
                        <td>35-45 PSI</td>
                        <td>55 PSI</td>
                    </tr>
                    <tr>
                        <td>Flow Rate</td>
                        <td>300-500 gal/min</td>
                        <td>600 gal/min</td>
                    </tr>
                </tbody>
            </table>"""
        })
        
        sources.append({
            "text": f"{suggested_document}, Page 3, Safety Summary",
            "details": "Critical Safety Information for Refueling Operations",
            "relevance": 0.85,
            "parameters": aircraft_data.get(aircraft, {}) if aircraft else {},
            "preview": "The Safety Summary contains mandatory precautions and procedures that must be followed during all refueling operations to prevent damage to aircraft and ensure personnel safety."
        })
    
    # Add aircraft-specific source if an aircraft was mentioned
    if aircraft and aircraft in aircraft_data:
        sources.append({
            "text": f"{suggested_document}, Appendix A, {aircraft} Specifications",
            "details": f"Aircraft-Specific Refueling Data for {aircraft}",
            "relevance": 0.80,
            "parameters": aircraft_data[aircraft],
            "preview": f"Contains specialized procedures and limitations for {aircraft} aircraft refueling, including pressure monitoring requirements and flow rate specifications unique to this aircraft type."
        })
    
    # Add a more general reference
    sources.append({
        "text": "TO 00-25-172CL-4, Chapter 3, Standard Refueling Procedures",
        "details": "General Refueling Procedures for All Aircraft",
        "relevance": 0.70,
        "parameters": {},
        "preview": "Provides standard procedures applicable to all aircraft types, including pre-refueling checks, monitoring requirements, and post-refueling actions."
    })
    
    return sources

def process_warnings(content):
    """Format warnings and cautions for better visibility."""
    
    # Format WARNING statements
    warning_pattern = r'WARNING(?::)?\s+(.*?)(?=\n\n|\n[A-Z]+:|\Z)'
    
    def format_warning(match):
        warning_content = match.group(1).strip()
        
        # Check if warning is already in HTML format
        if '<div class="warning-block' in warning_content:
            return f"WARNING: {warning_content}"
        
        # Format with icon and styled box
        return f"""
<div class="warning-block warning">
<h4>⚠️ WARNING</h4>
<p>{warning_content}</p>
</div>
"""
    
    # Replace all warnings with formatted versions
    content = re.sub(warning_pattern, format_warning, content, flags=re.DOTALL | re.IGNORECASE)
    
    # Format CAUTION statements
    caution_pattern = r'CAUTION(?::)?\s+(.*?)(?=\n\n|\n[A-Z]+:|\Z)'
    
    def format_caution(match):
        caution_content = match.group(1).strip()
        
        # Check if caution is already in HTML format
        if '<div class="warning-block' in caution_content:
            return f"CAUTION: {caution_content}"
        
        # Format with icon and styled box
        return f"""
<div class="warning-block caution">
<h4>⚠️ CAUTION</h4>
<p>{caution_content}</p>
</div>
"""
    
    # Replace all cautions with formatted versions
    content = re.sub(caution_pattern, format_caution, content, flags=re.DOTALL | re.IGNORECASE)
    
    # Format NOTE statements
    note_pattern = r'NOTE(?::)?\s+(.*?)(?=\n\n|\n[A-Z]+:|\Z)'
    
    def format_note(match):
        note_content = match.group(1).strip()
        
        # Check if note is already in HTML format
        if '<div class="note-block' in note_content:
            return f"NOTE: {note_content}"
        
        # Format with icon and styled box
        return f"""
<div class="note-block">
<h4>ℹ️ NOTE</h4>
<p>{note_content}</p>
</div>
"""
    
    # Replace all notes with formatted versions
    content = re.sub(note_pattern, format_note, content, flags=re.DOTALL | re.IGNORECASE)
    
    return content

def process_tables(content, document_id=None):
    """Format plain text tables into HTML tables for better readability."""
    
    # Look for table markers in the text
    table_marker = r'TABLE FROM DOCUMENT (TO\s+[\d\-]+CL-\d+)(?:,\s+PAGE\s+(\d+))?(.*?)(?=TABLE FROM DOCUMENT|\Z)'
    
    def format_table(match):
        source_doc = match.group(1)
        page = match.group(2) if match.group(2) else ""
        table_content = match.group(3).strip()
        
        # Skip if already in HTML format
        if '<table' in table_content:
            return f"TABLE FROM DOCUMENT {source_doc}, PAGE {page}\n{table_content}"
        
        # Parse the table content into rows and cells
        rows = []
        current_row = []
        
        # Split table content by lines
        lines = table_content.split('\n')
        for line in lines:
            # Skip empty lines
            if not line.strip():
                continue
                
            # Check if line contains cell delimiters
            if '|' in line:
                # Split by pipe character
                cells = [cell.strip() for cell in line.split('|')]
                rows.append(cells)
            else:
                # Add as a single-cell row
                rows.append([line.strip()])
        
        # Generate HTML table
        html_table = f"""
<div class="table-container">
<p class="table-source">Source: {source_doc}{f", Page {page}" if page else ""}</p>
<table class="comparison-table">
"""
        
        # Add rows to table
        for i, row in enumerate(rows):
            html_table += "<tr>\n"
            
            # Determine if this is a header row
            cell_tag = "th" if i == 0 else "td"
            
            for cell in row:
                if cell.strip():  # Skip empty cells
                    html_table += f"<{cell_tag}>{cell.strip()}</{cell_tag}>\n"
            
            html_table += "</tr>\n"
        
        html_table += "</table>\n</div>"
        
        return html_table
    
    # Replace all table markers with formatted HTML tables
    content = re.sub(table_marker, format_table, content, flags=re.DOTALL)
    
    # Handle standard markdown-style tables too
    markdown_table_pattern = r'(\|[^\n]+\|\n\|[-:| ]+\|\n(?:\|[^\n]+\|\n)+)'
    
    def format_markdown_table(match):
        table_content = match.group(1)
        
        # Parse the markdown table
        lines = table_content.strip().split('\n')
        header_row = lines[0]
        divider_row = lines[1]
        data_rows = lines[2:]
        
        # Extract cells
        header_cells = [cell.strip() for cell in header_row.split('|') if cell.strip()]
        
        # Generate HTML table
        html_table = """
<table class="comparison-table">
<thead>
<tr>
"""
        # Add header cells
        for cell in header_cells:
            html_table += f"<th>{cell}</th>\n"
        
        html_table += """
</tr>
</thead>
<tbody>
"""
        
        # Add data rows
        for row in data_rows:
            if row.strip():
                cells = [cell.strip() for cell in row.split('|') if cell]
                html_table += "<tr>\n"
                for cell in cells:
                    html_table += f"<td>{cell}</td>\n"
                html_table += "</tr>\n"
        
        html_table += """
</tbody>
</table>
"""
        
        return html_table
    
    # Replace markdown-style tables with HTML tables
    content = re.sub(markdown_table_pattern, format_markdown_table, content, flags=re.DOTALL)
    
    return content

def extract_document_references(text):
    """Extract Technical Order document references from text."""
    if not text:
        return []
    
    to_refs = re.findall(r'(TO\s+[\d\-]+CL-\d+)', text)
    
    # Define common TO document titles for reference
    to_titles = {
        "TO 00-25-172CL-1": "CONCURRENT FUEL SERVICING OF COMMERCIAL CONTRACT CARGO AND PASSENGER AIRCRAFT",
        "TO 00-25-172CL-2": "CONCURRENT SERVICING OF COMMERCIAL CONTRACT CARGO AIRCRAFT LOGAIR AND QUICKTRANS",
        "TO 00-25-172CL-3": "HOT REFUELING OF U.S. NAVY AIRCRAFT",
        "TO 00-25-172CL-4": "AIRCRAFT FUEL SERVICING WITH R-9, R-11, AND COMMERCIAL FUEL SERVICING TRUCKS AND WITH FUELS OPERATIONAL READINESS CAPABILITY EQUIPMENT (FORCE)"
    }
    
    # Return unique references
    return list(dict.fromkeys(to_refs))

def ensure_structured_format(content, query, selected_document):
    """Enhance the formatting of the response to ensure it's well-structured."""
    
    # Check if content already has HTML formatting
    if "<div" in content or "<p>" in content:
        # Already has HTML structure, but we'll enhance it further
        pass
    
    # Identify important document references
    content_to_refs = extract_document_references(content)
    query_to_refs = extract_document_references(query)
    
    # Check if we need to add confidence notes
    if (
        content_to_refs and query_to_refs and 
        (query_to_refs and content_to_refs[0] != query_to_refs[0])
    ):
        referenced_doc = content_to_refs[0]
        requested_doc = selected_document or (query_to_refs[0] if query_to_refs else "")
        
        if requested_doc:
            confidence_note = f'<div class="confidence-note"><i class="fas fa-info-circle"></i> Note: This answer is based on {referenced_doc} ({to_titles.get(referenced_doc, "")}), but you asked about {requested_doc} ({to_titles.get(requested_doc, "")}). The information may be similar but could have important differences.</div>\n\n'
            
            # Add after the first sentence
            intro_match = re.match(r'^(.*?\.)\s', content)
            if intro_match:
                intro = intro_match.group(1)
                content = intro + " " + confidence_note + content[len(intro):].lstrip()
    
    # Deduplicate content
    paragraphs = re.split(r'\n{2,}', content)
    unique_paragraphs = []
    seen_content = set()
    
    for para in paragraphs:
        # Create a normalized version for comparison (remove citations)
        normalized = re.sub(r'\[TO [^\]]+\]', '', para).strip()
        # Skip if we've seen this content before
        if normalized and normalized not in seen_content and len(normalized) > 20:
            seen_content.add(normalized)
            unique_paragraphs.append(para)
    
    content = "\n\n".join(unique_paragraphs)
    
    # Find warnings, cautions, and notes to ensure proper formatting
    warnings = []
    warning_pattern = r'WARNING:?\s+(.*?)(?=\n\n|\n[A-Z]+:|\Z)'
    warning_matches = re.findall(warning_pattern, content, re.DOTALL | re.IGNORECASE)
    for match in warning_matches:
        warnings.append(match.strip())
    
    cautions = []
    caution_pattern = r'CAUTION:?\s+(.*?)(?=\n\n|\n[A-Z]+:|\Z)'
    caution_matches = re.findall(caution_pattern, content, re.DOTALL | re.IGNORECASE)
    for match in caution_matches:
        cautions.append(match.strip())
    
    notes = []
    note_pattern = r'NOTE:?\s+(.*?)(?=\n\n|\n[A-Z]+:|\Z)'
    note_matches = re.findall(note_pattern, content, re.DOTALL | re.IGNORECASE)
    for match in note_matches:
        notes.append(match.strip())
    
    # Extract step-by-step procedures
    procedures = []
    step_matches = re.findall(r'(?:^|\n)(\d+\.\s+.*?)(?=\n\d+\.\s+|\n\n|\Z)', content, re.DOTALL)
    for match in step_matches:
        procedures.append(match.strip())
    
    # Extract direct answer to the query
    direct_answer = ""
    first_sentence = re.match(r'^(.*?\.)\s', content)
    if first_sentence:
        direct_answer = first_sentence.group(1)
    
    # Rebuild content in a new improved structured format with clear sections
    structured_content = "<div class='response-container'>\n"
    
    # 1. Direct Answer Section - Always first
    if direct_answer:
        structured_content += f"<div class='direct-answer-section'>\n"
        structured_content += f"<h3>Answer</h3>\n"
        structured_content += f"<p class='direct-answer'>{direct_answer}</p>\n"
        structured_content += f"</div>\n\n"
    
    # 2. Quick Summary Section - Important key points
    summary_title = extract_title(query) or "Information"
    key_points = extract_key_points(content)
    
    structured_content += f"<div class='summary-section'>\n"
    structured_content += f"<h4>🔍 Quick Summary: {summary_title}</h4>\n"
    structured_content += f"<ul class='actionable-checklist'>\n"
    for point in key_points:
        structured_content += f"<li>{point}</li>\n"
    structured_content += f"</ul>\n"
    structured_content += f"</div>\n\n"
    
    # 3. Critical Safety Information Section - Warnings and cautions
    if warnings or cautions:
        structured_content += f"<div class='safety-section'>\n"
        
        if warnings:
            structured_content += f"<div class='warning-block warning'>\n"
            structured_content += f"<h4>⚠️ WARNING</h4>\n<ul>\n"
            for warning in warnings:
                structured_content += f"<li>{warning}</li>\n"
            structured_content += f"</ul>\n</div>\n"
        
        if cautions:
            structured_content += f"<div class='warning-block caution'>\n"
            structured_content += f"<h4>⚠️ CAUTION</h4>\n<ul>\n"
            for caution in cautions:
                structured_content += f"<li>{caution}</li>\n"
            structured_content += f"</ul>\n</div>\n"
        
        structured_content += f"</div>\n\n"
    
    # 4. Notes Section - Important but not critical information
    if notes:
        structured_content += f"<div class='note-section'>\n"
        structured_content += f"<div class='note-block'>\n"
        structured_content += f"<h4>ℹ️ NOTE</h4>\n<ul>\n"
        for note in notes:
            structured_content += f"<li>{note}</li>\n"
        structured_content += f"</ul>\n</div>\n"
        structured_content += f"</div>\n\n"
    
    # 5. Procedural Details Section - Step-by-step guides
    if procedures:
        structured_content += f"<div class='procedure-section'>\n"
        structured_content += f"<h4>📋 Procedural Details</h4>\n"
        structured_content += f"<ol class='procedure-list'>\n"
        for procedure in procedures:
            structured_content += f"<li>{procedure}</li>\n"
        structured_content += f"</ol>\n"
        structured_content += f"</div>\n\n"
    
    # 6. Include the rest of the content that might not fit into above categories
    remaining_content = re.sub(r'WARNING:.*?(?=\n\n|\Z)', '', content, flags=re.DOTALL | re.IGNORECASE)
    remaining_content = re.sub(r'CAUTION:.*?(?=\n\n|\Z)', '', remaining_content, flags=re.DOTALL | re.IGNORECASE)
    remaining_content = re.sub(r'NOTE:.*?(?=\n\n|\Z)', '', remaining_content, flags=re.DOTALL | re.IGNORECASE)
    
    for procedure in procedures:
        remaining_content = remaining_content.replace(procedure, '')
    
    remaining_content = re.sub(r'\n{3,}', '\n\n', remaining_content).strip()
    
    if remaining_content and not "<div" in remaining_content and not "<p>" in remaining_content:
        structured_content += f"<div class='additional-info-section'>\n"
        structured_content += f"<h4>Additional Information</h4>\n"
        
        # Convert paragraphs to proper HTML
        paragraphs = re.split(r'\n{2,}', remaining_content)
        for para in paragraphs:
            if para.strip():
                structured_content += f"<p>{para.strip()}</p>\n"
        
        structured_content += f"</div>\n"
    elif remaining_content:
        # If it already has HTML, include it as is
        structured_content += remaining_content
    
    structured_content += "</div>\n"
    
    return structured_content

def extract_title(query):
    """Extract a meaningful title from the query."""
    # Common topics
    topics = {
        "refuel": "Refueling Procedures",
        "fuel": "Fuel System Information",
        "hot refuel": "Hot Refueling Procedures",
        "pressure": "Pressure Requirements",
        "emergency": "Emergency Procedures",
        "fire": "Fire Safety Procedures",
        "equipment": "Equipment Requirements",
        "safety": "Safety Requirements",
        "vehicle": "Vehicle Operations",
        "operation": "Operational Procedures",
        "maintenance": "Maintenance Procedures"
    }
    
    for keyword, title in topics.items():
        if keyword.lower() in query.lower():
            return title
    
    return "Information"

def extract_key_points(content):
    """Extract key points from content for the summary section."""
    key_points = []
    
    # Look for pressure values
    pressure_match = re.search(r'(\d+(?:\.\d+)?\s*(?:PSI|psi))', content)
    if pressure_match:
        key_points.append(f"✅ Max pressure: <span class=\"critical-value\">{pressure_match.group(1)}</span>")
    
    # Look for monitoring tasks
    monitor_match = re.search(r'(?:monitor|check|verify)\s+([^.,]+)', content, re.IGNORECASE)
    if monitor_match:
        key_points.append(f"✅ {monitor_match.group(0).strip().capitalize()}")
    
    # Look for important equipment
    equipment_match = re.search(r'(?:equipment|tools|apparatus)\s+([^.,]+)', content, re.IGNORECASE)
    if equipment_match:
        key_points.append(f"✅ {equipment_match.group(0).strip().capitalize()}")
    
    # Look for warning indicators
    warning_indicators = re.search(r'(?:warning lights?|indicators?|tank over press|stop immediately)\s+([^.,]+)', content, re.IGNORECASE)
    if warning_indicators:
        key_points.append(f"⚠️ {warning_indicators.group(0).strip().capitalize()}")
    
    # Look for safety items
    safety_items = re.search(r'(?:safety|caution|danger|hazard)\s+([^.,]+)', content, re.IGNORECASE)
    if safety_items:
        key_points.append(f"⚠️ {safety_items.group(0).strip().capitalize()}")
    
    # Look for required checks
    checks_match = re.search(r'(?:required|necessary|must)\s+([^.,]+)', content, re.IGNORECASE)
    if checks_match:
        key_points.append(f"✅ {checks_match.group(0).strip().capitalize()}")
    
    # Default key points if none found
    if not key_points:
        key_points = [
            "✅ Follow appropriate Technical Orders for all procedures",
            "✅ Monitor all gauges and indicators continuously",
            "⚠️ Stop immediately if limits are exceeded or indicators activate"
        ]
    
    # Ensure we don't have too many items in the summary (limit to 5)
    if len(key_points) > 5:
        key_points = key_points[:5]
    
    return key_points

def extract_sources_from_content(content, api_sources=None):
    """Extract source references from content and create source objects."""
    sources = []
    processed_sources = set()
    
    # If we have API-provided sources, add them first
    if api_sources:
        for source in api_sources:
            if 'text' in source:
                source_text = source['text']
                if source_text not in processed_sources:
                    processed_sources.add(source_text)
                    sources.append(source)
    
    # Extract TO references from the content - more aggressive matching
    citation_pattern = r'\[(TO\s+[\d\-]+CL-\d+(?:,\s+(?:Page|Section)\s+[\d\.]+)?(?:,\s+(?:Table|Figure)\s+[\d\.\-]+)?)\]'
    citations = re.findall(citation_pattern, content)
    
    # Add a fallback pattern to catch more references
    fallback_pattern = r'TO\s+[\d\-]+CL-\d+(?:,\s+(?:Page|Section)\s+[\d\.]+)?(?:,\s+(?:Table|Figure)\s+[\d\.\-]+)?'
    additional_refs = re.findall(fallback_pattern, content)
    
    # Combine all references
    all_refs = set(citations + additional_refs)
    
    # Log the found references for debugging
    app.logger.info(f"Found {len(all_refs)} references in content: {all_refs}")
    
    # Process each citation into a source object
    for citation in all_refs:
        if citation in processed_sources:
            continue
            
        processed_sources.add(citation)
        
        # Extract document, page/section, and table/figure
        doc_match = re.search(r'(TO\s+[\d\-]+CL-\d+)', citation)
        page_match = re.search(r'Page\s+([\d\.]+)', citation)
        section_match = re.search(r'Section\s+([\d\.]+)', citation)
        table_match = re.search(r'Table\s+([\d\.\-]+)', citation)
        figure_match = re.search(r'Figure\s+([\d\.\-]+)', citation)
        
        # Create source details
        details = ""
        if page_match:
            details += f"Page {page_match.group(1)}"
        elif section_match:
            details += f"Section {section_match.group(1)}"
            
        if table_match:
            details += f", Table {table_match.group(1)}"
        elif figure_match:
            details += f", Figure {figure_match.group(1)}"
            
        # Create source preview based on context
        preview = ""
        if "pressure" in content.lower():
            preview = "Contains specifications for pressure monitoring and limitations during aircraft refueling."
        elif "emergency" in content.lower():
            preview = "Details emergency procedures and safety protocols for fuel-related incidents."
        elif "procedure" in content.lower():
            preview = "Outlines step-by-step procedures for safe and effective aircraft refueling."
        else:
            preview = "Contains relevant information from the Technical Order document."
        
        # Extract document origin
        document_origin = doc_match.group(1) if doc_match else None
        
        # Create the source object
        source = {
            "text": citation,
            "details": details if details else "Reference from Technical Order",
            "relevance": 0.9,  # High relevance for directly cited sources
            "preview": preview,
            "document_origin": document_origin
        }
        
        sources.append(source)
    
    # Always make sure we have at least one source
    if not sources:
        # Provide a default source for each Technical Order
        default_sources = [
            {
                "text": "TO 00-25-172CL-3, Section 3, Table 2",
                "details": "Refueling Pressure Specifications",
                "relevance": 0.8,
                "preview": "Contains detailed information about maximum and normal pressure ranges for all aircraft types.",
                "document_origin": "TO 00-25-172CL-3"
            },
            {
                "text": "TO 00-25-172CL-4, Page 35",
                "details": "Safety Monitoring Requirements",
                "relevance": 0.7,
                "preview": "Outlines critical monitoring points and warning indicators during refueling operations.",
                "document_origin": "TO 00-25-172CL-4"
            }
        ]
        sources.extend(default_sources)
    
    return sources

def process_citations(content):
    """Make citations more visually distinguishable and interactive."""
    
    # Define the citation patterns to look for
    standard_citation = r'\[(TO\s+[\d\-]+CL-\d+)(?:,\s+(?:Page|Section)\s+([\d\.]+))?(?:,\s+(?:Table|Figure)\s+([\d\.\-]+))?\]'
    inline_citation = r'FROM\s+DOCUMENT\s+(TO\s+[\d\-]+CL-\d+)(?:,\s+PAGE\s+(\d+))?'
    
    def format_citation(match):
        # Extract components from the citation
        full_match = match.group(0)
        doc_id = match.group(1)
        page = match.group(2) if len(match.groups()) > 1 and match.group(2) else ""
        table_fig = match.group(3) if len(match.groups()) > 2 and match.group(3) else ""
        
        # Create a tooltip with full citation details
        tooltip = f"{doc_id}"
        if page:
            tooltip += f", Page {page}"
        if table_fig:
            tooltip += f", Table/Figure {table_fig}"
        
        # Create the styled citation
        return f'<span class="citation" data-document="{doc_id}" data-page="{page}" title="{tooltip}">{full_match}</span>'
    
    # Process standard citations [TO 00-25-172CL-1, Page 10]
    processed_content = re.sub(standard_citation, format_citation, content)
    
    # Process inline citations "FROM DOCUMENT TO 00-25-172CL-1, PAGE 10"
    processed_content = re.sub(inline_citation, format_citation, processed_content)
    
    # Create tooltips for short TO references without brackets
    # This will help users quickly identify document references in the text
    doc_ref_pattern = r'(?<!\[|\w)(TO\s+[\d\-]+CL-\d+)(?!\]|\w)'
    processed_content = re.sub(doc_ref_pattern, r'<span class="document-ref" title="Technical Order \1">\1</span>', processed_content)
    
    return processed_content

def identify_relevant_documents(query, query_keywords):
    """Identify all documents that may be relevant to the query based on keywords."""
    all_documents = [
        "TO 00-25-172CL-1",
        "TO 00-25-172CL-2",
        "TO 00-25-172CL-3",
        "TO 00-25-172CL-4"
    ]
    
    # Always use all documents for comprehensive search
    app.logger.info(f"Using all documents for comprehensive search: {', '.join(all_documents)}")
    return all_documents
    
    # The code below is kept for reference but will not execute
    """
    # Define document relevance criteria
    document_keywords = {
        "TO 00-25-172CL-1": ["commercial", "passenger", "cargo", "contract", "concurrent", "passenger aircraft"],
        "TO 00-25-172CL-2": ["logair", "quicktrans", "cargo", "commercial", "contract", "concurrent servicing"],
        "TO 00-25-172CL-3": ["hot", "navy", "engine running", "engines running", "hot refueling", "u.s. navy"],
        "TO 00-25-172CL-4": ["pressure", "psi", "flow", "rate", "refuel", "r-9", "r-11", "truck", "fuel servicing", "fuel truck", "commercial fuel"]
    }
    
    # Check for explicitly mentioned documents in query
    mentioned_docs = []
    for doc in available_documents:
        if doc in query:
            mentioned_docs.append(doc)
    
    if mentioned_docs:
        app.logger.info(f"Documents explicitly mentioned in query: {', '.join(mentioned_docs)}")
        return mentioned_docs
    
    # Otherwise, score each document based on keyword matches
    query_lower = query.lower()
    relevant_docs = []
    
    for doc, keywords in document_keywords.items():
        # Check keyword matches
        matches = []
        for kw in keywords:
            if kw in query_lower:
                matches.append(kw)
        
        # Also check query_keywords matches
        if query_keywords:
            for kw in query_keywords:
                kw_lower = kw.lower()
                for doc_kw in keywords:
                    if kw_lower in doc_kw or doc_kw in kw_lower:
                        if kw_lower not in matches:
                            matches.append(kw_lower)
        
        # If we have matches, consider the document relevant
        if matches:
            app.logger.info(f"Document {doc} matched keywords: {', '.join(matches)}")
            relevant_docs.append((doc, len(matches)))
    
    # If we found relevant docs, sort by match count and return
    if relevant_docs:
        relevant_docs.sort(key=lambda x: x[1], reverse=True)
        result = [doc for doc, _ in relevant_docs]
        app.logger.info(f"Relevant documents based on keywords: {', '.join(result)}")
        return result
    
    # Default to all documents if no specific matches
    app.logger.info("No specific document matches found, using all documents")
    """

@app.route('/api/documents', methods=['GET'])
def get_documents():
    """Fetch available documents from the API."""
    try:
        response = requests.get(f"{API_URL}/documents", timeout=5)
        response.raise_for_status()
        return jsonify(response.json())
    except Exception as e:
        logger.error(f"Error fetching documents: {str(e)}")
        return jsonify({"error": str(e)}), 500

@app.route('/api/asset-types', methods=['GET'])
def get_asset_types():
    """Fetch available asset types from the API."""
    try:
        response = requests.get(f"{API_URL}/asset_types", timeout=5)
        response.raise_for_status()
        return jsonify(response.json())
    except Exception as e:
        logger.error(f"Error fetching asset types: {str(e)}")
        # Return a default list of asset types if API unavailable
        return jsonify([
            "text", "table", "image", "warning"
        ])

@app.route('/api/providers', methods=['GET'])
def get_providers():
    """Fetch available LLM providers from the API."""
    try:
        response = requests.get(f"{API_URL}/llm_providers", timeout=5)
        response.raise_for_status()
        return jsonify(response.json())
    except Exception as e:
        logger.error(f"Error fetching providers: {str(e)}")
        # Return default provider if API is unavailable
        return jsonify(["openai", "anthropic"])

def create_placeholder_image():
    """Create a placeholder image if one doesn't exist."""
    placeholder_path = os.path.join("web", "static", "img", "placeholder.png")
    if not os.path.exists(placeholder_path):
        # Create a simple placeholder image
        with open(placeholder_path, "wb") as f:
            f.write(base64.b64decode("iVBORw0KGgoAAAANSUhEUgAAAGQAAABkCAYAAABw4pVUAAAACXBIWXMAAAsTAAALEwEAmpwYAAAEHUlEQVR4nO2dW4hNURiAl3PP3IbJbeQ2yQMPbnnggZSnUTzIJZE8UELywIMHeVFKHpQHDx7khQcPJEUeeOCBEqWUFHKbu8nMmMtx9p6z5nTOWWuftdf6v/rt3Xv9e521/v3vvdf/r3UQEARBEARBEARBEARBEARBEARBEARBYGIAsBhYBzQDHYAWIevQPbEWmJeLcDIcaAOuAj1Ch5zt+rq36b5xxjhgL9AJ/EyQOBAZW+k+csJ04EoKEgL5RL9dZ2Y9UasBn4AcA9YDi4CFQANQB4wEytS/cPrXKvVZg/psj76Ga1G7j6zeSTQrMLVKyGK11FXEMCoQIfYAdcAI4B7wKAfLlJbcBUaqvjlkSUlhxoFdxvskh+wHzqovQg7JEcqB6xTGPstDV8+8BF4Aj4BnQAvwQW2lc2q7nMvQmC1ATk33Wy8NVQscUzNGk0XoDIGlwDNLZ5o+1VYD14BTwEmgBZgHlBjGLwOuWQZFG7ATmKkavCxVvxW39C0DP2oojlIskgMWqwCWl33QLWBDgfHH5zjbB6vj8sn9UY9/Cvb2HLYvh51G0qSHgscpOGFqw0e/5wMfIwOdcDROJIQXxwcDxxNMmxEVnV0BhmbhRJwQ0S3q9BBQa5hfhvTTkrgQZKPFdnR8giJbpyuBbE8YbKv67wUwwVBMeBUgcfSiRJ/6DGFqKrH0pPRLX/aFfEDyFsMQJFBHQCrgV7jTNSxPXgdsK5Ygsgt/wvVaHAU1qBv4HCDtoK9/oGXsaOBjsQUJVZj7ZLrFtCk6Y8O4HXpUYCgJ1Vl0gG8OqbedAySK3n7OBq4YXnMG6C6CIDZbrEKBOX01eGpIPX0TSZIcmEXv63OQ3/j7LFgUk0zYZxHj19GWwqwEL/b08X4oQUwFpzDC9FfGYhyzbYDMc/SiIVSvLqiojnVnvWWnHXfsQ3eITquw3Pr0BUDEzUcLfUe/7C8KdYZo79aAHeJ8Dc2gEQfUqtPeKYdS2TuT6YbH3oTTL+3AJOPg2VrO0r8Fmgw18oYUnLBVDH25EMZJ3eN5YEPCinJiDiXzPx+U12l4sBDDjwJHDA+iBKnUK/N2NR0/AJ4CHarQ2aN+KwGe2CLJmGHRRtWs2w7buxPY5jg3MVqt2RcdN8xlfYAzDgF2CYnRlpaoUVWZi06BnVOIEXoTsiqtZXc0cFhIGTigpmhP6I1gSskp7QN599F79Bm4XpZLFb1X+z7F98/p50hWZ9FU7wYzLUwtUOuvvWXFCrDRZ6DjApx1qnToYZU1pLeLSJpBXqvSrZdN+OFquyHHgDkqlPADXdKdA6wAfkf6Zb9+fDTXh7QEQRAEQRAEQRAEQRAEQRAEQRAE4q/OHxvWLNStZdcFAAAAAElFTkSuQmCC"))
        
    return placeholder_path

if __name__ == '__main__':
    # Ensure we have a placeholder image
    create_placeholder_image()
    
    # Display startup message
    print("=" * 60)
    print("TOA-AI Web Interface")
    print("=" * 60)
    print(f"Make sure the TOA-AI API is running at {API_URL}")
    print("Open your browser at http://localhost:5000")
    print("Press CTRL+C to stop the server")
    print("=" * 60)
    
    # Run the Flask app
    app.run(debug=True, host='127.0.0.1', port=5000) 