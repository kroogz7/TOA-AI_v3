$(document).ready(function() {
    // DOM Elements
    const chatMessages = $('#chat-messages');
    const messageForm = $('#message-form');
    const chatInput = $('#chat-input');
    const resetButton = $('#reset-button');
    const sendButton = $('#send-button');
    const sourcesContainer = $('#sources-container');
    const connectionStatus = $('#connection-status');
    
    // Template elements
    const userMessageTemplate = document.getElementById('user-message-template');
    const assistantMessageTemplate = document.getElementById('assistant-message-template');
    
    // Keep track of connection status
    let isOnline = false;
    
    // Prevent default form submission - very important
    messageForm.attr('onsubmit', 'return false;');
    
    // Display offline mode message initially
    addSystemMessage("Operating in offline mode with cached Technical Order information. Ask questions about aircraft maintenance and refueling procedures.");
    
    // Event listeners
    messageForm.on('submit', function(event) {
        event.preventDefault(); // Prevent form submission
        return handleChatSubmit();
    });
    
    sendButton.on('click', function(event) {
        event.preventDefault(); // Prevent button default
        handleChatSubmit();
    });
    
    resetButton.on('click', function() {
        chatInput.val('');
        chatInput.focus();
    });
    
    // Handle form submission logic
    function handleChatSubmit() {
        const message = chatInput.val().trim();
        if (!message) return false;
        
        // Add user message
        addUserMessage(message);
        
        // Clear input
        chatInput.val('');
        
        // Show loading indicator
        showLoading();
        
        // Send to backend
        sendChatRequest(message);
        
        return false; // Prevent form submission
    }
    
    // Functions
    function addUserMessage(text) {
        // Clone the template
        const template = $(userMessageTemplate.content.cloneNode(true));
        template.find('p').text(text);
        chatMessages.append(template);
        scrollToBottom();
    }
    
    function addAssistantMessage(content) {
        // Clone the template
        const template = $(assistantMessageTemplate.content.cloneNode(true));
        template.find('.message-text').html(content); // Use html to render formatted content
        chatMessages.append(template);
        scrollToBottom();
    }
    
    function addSystemMessage(text) {
        const messageHtml = `
            <div class="message system">
                <div class="message-content">
                    <p>${text}</p>
                </div>
            </div>`;
        chatMessages.append(messageHtml);
        scrollToBottom();
    }
    
    function showLoading() {
        const loadingHtml = `
            <div id="loading-indicator" class="message system">
                <div class="message-content">
                    <p><i class="fas fa-spinner fa-spin"></i> Retrieving information...</p>
                </div>
            </div>`;
        chatMessages.append(loadingHtml);
        scrollToBottom();
    }
    
    function hideLoading() {
        $('#loading-indicator').remove();
    }
    
    function scrollToBottom() {
        const container = chatMessages[0];
        if (container) {
            container.scrollTop = container.scrollHeight;
        }
    }
    
    function updateSourcesPanel(sources) {
        // Clear existing sources
        sourcesContainer.empty();
        
        // Check if we have any sources
        if (!sources || sources.length === 0) {
            sourcesContainer.html('<p class="text-muted">No specific sources available for this response.</p>');
            return;
        }
        
        // Group sources by document
        const groupedSources = {};
        sources.forEach(source => {
            const docId = source.document || 'unknown';
            if (!groupedSources[docId]) {
                groupedSources[docId] = [];
            }
            groupedSources[docId].push(source);
        });
        
        // Create accordion for sources
        let accordionHtml = '<div class="accordion" id="sourcesAccordion">';
        
        // Counter for accordion items
        let counter = 0;
        
        // Add sources by document group
        for (const docId in groupedSources) {
            const docSources = groupedSources[docId];
            const firstSource = docSources[0];
            const docTitle = firstSource.title || docId;
            
            // Create accordion item
            accordionHtml += `
                <div class="accordion-item source-item" data-document="${docId}" data-title="${docTitle}">
                    <h2 class="accordion-header" id="heading${counter}">
                        <button class="accordion-button ${counter === 0 ? '' : 'collapsed'}" type="button" data-bs-toggle="collapse" data-bs-target="#collapse${counter}" aria-expanded="${counter === 0 ? 'true' : 'false'}" aria-controls="collapse${counter}">
                            <div class="source-header">
                                <div class="source-document">${docId}</div>
                                <div class="source-title">${docTitle}</div>
                            </div>
                        </button>
                    </h2>
                    <div id="collapse${counter}" class="accordion-collapse collapse ${counter === 0 ? 'show' : ''}" aria-labelledby="heading${counter}" data-bs-parent="#sourcesAccordion">
                        <div class="accordion-body">
                            <ul class="source-details-list">
            `;
            
            // Add each source detail
            docSources.forEach(source => {
                const relevance = source.relevance ? `<span class="relevance-score">${Math.round(source.relevance * 100)}% match</span>` : '';
                const content = source.content || '';
                const page = source.page ? `<span class="source-page">Page ${source.page}</span>` : '';
                const section = source.section ? `<span class="source-section">Section ${source.section}</span>` : '';
                
                accordionHtml += `
                    <li class="source-detail">
                        <div class="source-metadata">
                            ${page} ${section} ${relevance}
                        </div>
                        <div class="source-content">
                            ${content}
                        </div>
                    </li>
                `;
            });
            
            // Close accordion item
            accordionHtml += `
                            </ul>
                        </div>
                    </div>
                </div>
            `;
            
            counter++;
        }
        
        // Close accordion
        accordionHtml += '</div>';
        
        // Add to sources container
        sourcesContainer.html(accordionHtml);
    }
    
    function sendChatRequest(message) {
        // Show loading indicator
        showLoading();
        
        // Get selected document if any
        const selectedDocument = $('#document-selector').val();
        
        // Send AJAX request
        $.ajax({
            url: '/chat',
            type: 'POST',
            contentType: 'application/json',
            data: JSON.stringify({ 
                message: message,
                document: selectedDocument
            }),
            success: function(data) {
                // Log response for debugging
                console.log("Response data:", data);
                
                // Hide loading indicator
                hideLoading();
                
                // Update connection status based on API availability
                updateConnectionStatus(data.api_available);
                
                // Extract response content from data
                let response = "";
                if (data.response) {
                    response = data.response;
                } else if (data.answer) {
                    response = data.answer;
                } else if (data.content) {
                    response = data.content;
                } else if (data.html) {
                    response = data.html;
                } else if (data.text) {
                    response = data.text;
                } else if (data.message) {
                    response = data.message;
                } else if (data.result) {
                    response = data.result;
                } else if (data.output) {
                    response = data.output;
                } else {
                    response = "Received empty response from server.";
                }
                
                // Add assistant message with the response
                addAssistantMessage(response);
                
                // Update sources panel
                updateSourcesPanel(data.sources || []);
                
                // Enhance citations with interactive features
                enhanceCitationInteractivity();
            },
            error: function(xhr, status, error) {
                // Hide loading indicator
                hideLoading();
                
                // Update connection status to offline
                updateConnectionStatus(false);
                
                // Log error
                console.error("Error:", error);
                
                // Add error message
                addAssistantMessage("Sorry, there was an error processing your request. Please try again.");
            }
        });
    }
    
    // Function to update connection status indicator
    function updateConnectionStatus(apiAvailable) {
        isOnline = apiAvailable;
        
        if (isOnline) {
            // Update to online mode
            connectionStatus.html('<span class="status-indicator online"><i class="fas fa-wifi"></i> ONLINE MODE - Connected to Technical Order database</span>');
        } else {
            // Update to offline mode
            connectionStatus.html('<span class="status-indicator offline"><i class="fas fa-wifi"></i> OFFLINE MODE - Using cached Technical Order information</span>');
        }
    }
    
    // Function to enhance citation interactivity after response is added
    function enhanceCitationInteractivity() {
        // Add click handlers to all citations
        $('.citation').on('click', function() {
            const docId = $(this).data('document');
            const page = $(this).data('page');
            
            // If document selector exists, set it to this document
            if ($('#document-selector').length && docId) {
                $('#document-selector').val(docId);
            }
            
            // Highlight this citation
            $('.citation').removeClass('citation-highlighted');
            $(this).addClass('citation-highlighted');
            
            // Scroll to related source in the sources panel if possible
            if (docId) {
                const sourceElement = $(`.source-item[data-document="${docId}"]`);
                if (sourceElement.length) {
                    // Open the sources panel if it's not already open
                    if (!$('#sources-panel').is(':visible')) {
                        $('#toggle-sources-btn').click();
                    }
                    
                    // Scroll to the source
                    $('#sources-container').animate({
                        scrollTop: sourceElement.position().top
                    }, 500);
                    
                    // Highlight the source briefly
                    sourceElement.addClass('source-highlight');
                    setTimeout(() => {
                        sourceElement.removeClass('source-highlight');
                    }, 2000);
                }
            }
        });
        
        // Add tooltips for document references
        $('.document-ref').on('mouseover', function() {
            const docId = $(this).text();
            const sourcesData = $('.source-item[data-document="' + docId + '"]');
            
            if (sourcesData.length) {
                const title = sourcesData.data('title') || 'Technical Order';
                $(this).attr('title', `${title}`);
            }
        });
    }
}); 