// src/utils/templateDownloadUtils.js
/**
 * Template download utilities for frontend
 * Handles template detection, download link parsing, and file downloads
 */

// Template type mappings
const TEMPLATE_TYPES = {
  vacation: {
    keywords: ['məzuniyyət', 'vacation', 'tətil', 'istirahət', 'məzuniyət'],
    azName: 'Məzuniyyət Ərizəsi',
    defaultFilename: 'mezuniyyet_erizesi'
  },
  business_trip: {
    keywords: ['ezamiyyət', 'business_trip', 'səfər', 'komandirovka', 'ezamiyyet'],
    azName: 'Ezamiyyət Ərizəsi', 
    defaultFilename: 'ezamiyyet_erizesi'
  },
  contract: {
    keywords: ['müqavilə', 'contract', 'razılaşma', 'saziş', 'muqavile'],
    azName: 'Müqavilə Şablonu',
    defaultFilename: 'muqavile_sablonu'
  },
  memorandum: {
    keywords: ['memorandum', 'anlaşma', 'razılaşma', 'anlasma'],
    azName: 'Anlaşma Memorandumu',
    defaultFilename: 'anlasma_memorandumu'
  }
};

// Download link patterns
const DOWNLOAD_LINK_PATTERNS = [
  // Markdown links: [text](url) - prioritized pattern
  {
    regex: /\[([^\]]+)\]\((https?:\/\/[^\)]+)\)/g,
    textIndex: 1,
    urlIndex: 2,
    type: 'markdown',
    priority: 1
  },
  // Direct URLs with emoji context
  {
    regex: /📥[^:]*:?[\s]*(https?:\/\/[^\s\n]+)/gi,
    textIndex: null,
    urlIndex: 1,
    type: 'emoji_direct',
    defaultText: 'Yüklə',
    priority: 2
  },
  // Bold download links
  {
    regex: /\*\*[^*]*yükləmə[^*]*linki[^*]*\*\*[\s]*:?[\s]*(https?:\/\/[^\s\n]+)/gi,
    textIndex: null,
    urlIndex: 1,
    type: 'bold_direct',
    defaultText: 'Yükləmə linki',
    priority: 3
  },
  // Simple URL after download keywords
  {
    regex: /(yükləmə linki|download link|yüklə)[\s]*:?[\s]*(https?:\/\/[^\s\n]+)/gi,
    textIndex: 1,
    urlIndex: 2,
    type: 'keyword_direct',
    priority: 4
  }
];

/**
 * Template Download Handler
 */
export const TemplateDownloadHandler = {
  
  /**
   * Parse download links from message content with improved priority handling
   * @param {string} content - Message content to parse
   * @returns {Array} Array of download link objects
   */
  parseDownloadLinks: (content) => {
    const links = [];
    const processedUrls = new Set(); // Avoid duplicates
    
    // Sort patterns by priority
    const sortedPatterns = DOWNLOAD_LINK_PATTERNS.sort((a, b) => (a.priority || 99) - (b.priority || 99));
    
    sortedPatterns.forEach(pattern => {
      let match;
      const regex = new RegExp(pattern.regex.source, pattern.regex.flags);
      
      while ((match = regex.exec(content)) !== null) {
        const url = match[pattern.urlIndex];
        
        // Skip if URL already processed
        if (processedUrls.has(url)) continue;
        
        // Validate URL format
        if (!url || !url.startsWith('http')) continue;
        
        processedUrls.add(url);
        
        const text = pattern.textIndex !== null 
          ? match[pattern.textIndex].trim()
          : pattern.defaultText || 'Yüklə';
        
        links.push({
          text: text,
          url: url.trim(),
          type: pattern.type,
          fullMatch: match[0],
          priority: pattern.priority || 99
        });
      }
    });
    
    // Sort by priority and return
    return links.sort((a, b) => a.priority - b.priority);
  },

  /**
   * Download file from URL
   * @param {string} url - Download URL
   * @param {string} filename - Optional filename
   * @returns {Promise<boolean>} Success status
   */
  downloadFromUrl: async (url, filename = null) => {
    try {
      const response = await fetch(url, {
        method: 'GET',
        credentials: 'include',
        headers: {
          'Accept': 'application/octet-stream'
        }
      });
      
      if (!response.ok) {
        throw new Error(`Download failed: ${response.status} ${response.statusText}`);
      }
      
      const blob = await response.blob();
      
      // Try to get filename from response headers
      if (!filename) {
        const contentDisposition = response.headers.get('Content-Disposition');
        if (contentDisposition) {
          const match = contentDisposition.match(/filename[^;=\n]*=((['"]).*?\2|[^;\n]*)/);
          if (match && match[1]) {
            filename = match[1].replace(/['"]/g, '');
          }
        }
        
        // Fallback to URL-based filename
        if (!filename) {
          const urlPath = new URL(url).pathname;
          filename = urlPath.split('/').pop() || 'download';
        }
      }
      
      // Ensure filename has extension
      if (!filename.includes('.')) {
        filename += '.docx';
      }
      
      // Create and trigger download
      const downloadUrl = window.URL.createObjectURL(blob);
      const link = document.createElement('a');
      link.href = downloadUrl;
      link.download = filename;
      link.style.display = 'none';
      
      document.body.appendChild(link);
      link.click();
      
      // Cleanup
      setTimeout(() => {
        window.URL.revokeObjectURL(downloadUrl);
        document.body.removeChild(link);
      }, 100);
      
      return true;
      
    } catch (error) {
      console.error('Download error:', error);
      throw new Error(`Yükləmə xətası: ${error.message}`);
    }
  },

  /**
   * Get file extension from URL or content type
   * @param {string} url - URL to analyze
   * @returns {string} File extension
   */
  getFileExtension: (url) => {
    try {
      const pathname = new URL(url).pathname;
      const extension = pathname.split('.').pop();
      return extension && extension.length <= 4 ? extension : 'docx';
    } catch (error) {
      return 'docx';
    }
  },

  /**
   * Generate clean filename from template name
   * @param {string} templateName - Template name
   * @param {string} extension - File extension
   * @returns {string} Clean filename
   */
  generateFilename: (templateName, extension = 'docx') => {
    const cleanName = templateName
      .toLowerCase()
      .replace(/[^a-z0-9əıöüçşğ\s]/g, '') // Keep Azerbaijani characters
      .replace(/\s+/g, '_')
      .replace(/_{2,}/g, '_')
      .replace(/^_|_$/g, '');
    
    return `${cleanName || 'template'}.${extension}`;
  },

  /**
   * Create download button element
   * @param {Object} linkInfo - Link information
   * @param {Function} onDownload - Download callback
   * @returns {HTMLElement} Button element
   */
  createDownloadButton: (linkInfo, onDownload) => {
    const button = document.createElement('button');
    button.className = `
      w-full flex items-center justify-between p-3 bg-white border border-blue-300 
      rounded-lg hover:bg-blue-50 hover:border-blue-400 transition-colors group
    `.trim();
    
    button.innerHTML = `
      <div class="flex items-center">
        <svg class="w-4 h-4 text-blue-600 mr-3" viewBox="0 0 24 24" fill="currentColor">
          <path d="M19 9h-4V3H9v6H5l7 7 7-7zM5 18v2h14v-2H5z"/>
        </svg>
        <span class="text-sm font-medium text-blue-900">${linkInfo.text}</span>
      </div>
      <svg class="w-4 h-4 text-blue-500 opacity-0 group-hover:opacity-100 transition-opacity" viewBox="0 0 24 24" fill="none" stroke="currentColor">
        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M10 6H6a2 2 0 00-2 2v10a2 2 0 002 2h10a2 2 0 002-2v-4M14 4h6m0 0v6m0-6L10 14"/>
      </svg>
    `;
    
    button.addEventListener('click', async (e) => {
      e.preventDefault();
      try {
        button.disabled = true;
        button.style.opacity = '0.6';
        await onDownload(linkInfo.url, linkInfo.text);
      } catch (error) {
        console.error('Download failed:', error);
        throw error;
      } finally {
        button.disabled = false;
        button.style.opacity = '1';
      }
    });
    
    return button;
  },

  /**
   * Create download section with multiple buttons
   * @param {Array} links - Array of download links
   * @param {Function} onDownload - Download callback
   * @returns {HTMLElement} Download section element
   */
  createDownloadSection: (links, onDownload) => {
    if (!links || links.length === 0) return null;
    
    const section = document.createElement('div');
    section.className = 'mt-4 p-4 bg-blue-50 border border-blue-200 rounded-lg';
    
    const header = document.createElement('div');
    header.className = 'flex items-center mb-2';
    header.innerHTML = `
      <svg class="w-5 h-5 text-blue-600 mr-2" viewBox="0 0 24 24" fill="currentColor">
        <path d="M14,2H6A2,2 0 0,0 4,4V20A2,2 0 0,0 6,22H18A2,2 0 0,0 20,20V8L14,2M18,20H6V4H13V9H18V20Z" />
      </svg>
      <span class="font-medium text-blue-900">
        ${links.length === 1 ? 'Sənəd yükləmə' : `${links.length} sənəd mövcuddur`}
      </span>
    `;
    
    const buttonsContainer = document.createElement('div');
    buttonsContainer.className = 'space-y-2';
    
    links.forEach(link => {
      const button = TemplateDownloadHandler.createDownloadButton(link, onDownload);
      buttonsContainer.appendChild(button);
    });
    
    const footer = document.createElement('div');
    footer.className = 'mt-3 flex items-center text-xs text-blue-700';
    footer.innerHTML = `
      <svg class="w-3 h-3 mr-1" viewBox="0 0 24 24" fill="currentColor">
        <path d="M11,9H13V7H11M12,20C7.59,20 4,16.41 4,12C4,7.59 7.59,4 12,4C16.41,4 20,7.59 20,12C20,16.41 16.41,20 12,20M12,2A10,10 0 0,0 2,12A10,10 0 0,0 12,22A10,10 0 0,0 22,12A10,10 0 0,0 12,2M11,17H13V11H11V17Z" />
      </svg>
      <span>Yüklənən fayllar brauzerin default qovluğuna saxlanacaq</span>
    `;
    
    section.appendChild(header);
    section.appendChild(buttonsContainer);
    section.appendChild(footer);
    
    return section;
  }
};

/**
 * Template Type Detector
 */
export const TemplateTypeDetector = {
  
  /**
   * Detect template type from message content
   * @param {string} message - Message to analyze
   * @returns {string|null} Template type or null
   */
  detect: (message) => {
    const messageLower = message.toLowerCase();
    
    for (const [type, config] of Object.entries(TEMPLATE_TYPES)) {
      if (config.keywords.some(keyword => messageLower.includes(keyword))) {
        return type;
      }
    }
    
    return null;
  },

  /**
   * Check if message is a template request
   * @param {string} message - Message to check
   * @returns {boolean} Is template request
   */
  isTemplateRequest: (message) => {
    const templateKeywords = ['nümunə', 'template', 'şablon', 'sablon'];
    const actionKeywords = ['yüklə', 'download', 'link', 'ver', 'göstər'];
    
    const messageLower = message.toLowerCase();
    
    const hasTemplateKeyword = templateKeywords.some(kw => messageLower.includes(kw));
    const hasActionKeyword = actionKeywords.some(kw => messageLower.includes(kw));
    const hasTemplateType = TemplateTypeDetector.detect(message) !== null;
    
    return hasTemplateType && (hasTemplateKeyword || hasActionKeyword);
  },

  /**
   * Get template info by type
   * @param {string} type - Template type
   * @returns {Object|null} Template info
   */
  getTemplateInfo: (type) => {
    return TEMPLATE_TYPES[type] || null;
  },

  /**
   * Get all template types
   * @returns {Object} All template types
   */
  getAllTypes: () => {
    return { ...TEMPLATE_TYPES };
  }
};

/**
 * Message Content Processor
 */
export const MessageContentProcessor = {
  
  /**
   * Process message content and extract download info
   * @param {string} content - Message content
   * @returns {Object} Processed content info
   */
  processContent: (content) => {
    const downloadLinks = TemplateDownloadHandler.parseDownloadLinks(content);
    const templateType = TemplateTypeDetector.detect(content);
    const isTemplateRequest = TemplateTypeDetector.isTemplateRequest(content);
    
    return {
      originalContent: content,
      downloadLinks,
      templateType,
      isTemplateRequest,
      hasDownloads: downloadLinks.length > 0,
      cleanContent: MessageContentProcessor.removeDownloadLinks(content, downloadLinks)
    };
  },

  /**
   * Remove download links from content for clean display
   * @param {string} content - Original content
   * @param {Array} links - Download links to remove
   * @returns {string} Clean content
   */
  removeDownloadLinks: (content, links) => {
    let cleanContent = content;
    
    links.forEach(link => {
      if (link.fullMatch) {
        cleanContent = cleanContent.replace(link.fullMatch, '');
      }
    });
    
    // Clean up extra whitespace and line breaks
    return cleanContent
      .replace(/\n{3,}/g, '\n\n')
      .replace(/\s{2,}/g, ' ')
      .trim();
  }
};

/**
 * Default export with all utilities
 */
export default {
  TemplateDownloadHandler,
  TemplateTypeDetector,
  MessageContentProcessor,
  TEMPLATE_TYPES,
  DOWNLOAD_LINK_PATTERNS
};