const { ipcRenderer } = require('electron');

// Load the JSON data from categories.json
fetch('categories.json')
  .then(res => res.json())
  .then(data => {
    const container = document.getElementById('categoryContainer');

    // Create parent checkbox
    const parentDiv = document.createElement('div');
    parentDiv.className = 'form-check mb-2';

    const parentCheckbox = document.createElement('input');
    parentCheckbox.className = 'form-check-input';
    parentCheckbox.type = 'checkbox';
    parentCheckbox.id = 'parent-checkbox';

    const parentLabel = document.createElement('label');
    parentLabel.className = 'form-check-label fw-bold';
    parentLabel.htmlFor = 'parent-checkbox';
    parentLabel.innerText = data.name;

    parentDiv.appendChild(parentCheckbox);
    parentDiv.appendChild(parentLabel);
    container.appendChild(parentDiv);

    // Create child checkboxes
    const childContainer = document.createElement('div');
    childContainer.className = 'ps-4';
    data.children.forEach((child, index) => {
      const childDiv = document.createElement('div');
      childDiv.className = 'form-check';

      const childCheckbox = document.createElement('input');
      childCheckbox.className = 'form-check-input';
      childCheckbox.type = 'checkbox';
      childCheckbox.id = `child-${index}`;
      childCheckbox.dataset.url = child.url;

      const childLabel = document.createElement('label');
      childLabel.className = 'form-check-label';
      childLabel.htmlFor = `child-${index}`;
      childLabel.innerText = child.name;

      childDiv.appendChild(childCheckbox);
      childDiv.appendChild(childLabel);
      childContainer.appendChild(childDiv);
    });

    container.appendChild(childContainer);

    // Uncheck all children if parent is unchecked
    parentCheckbox.addEventListener('change', () => {
      const children = childContainer.querySelectorAll('input[type="checkbox"]');
      children.forEach(cb => cb.checked = parentCheckbox.checked);
    });
  })
  .catch(err => {
    document.getElementById('categoryContainer').innerText = '❌ Failed to load categories.';
    console.error('Error loading categories.json:', err);
  });


// Timer functionality
let startTime;
let timerInterval;
let progressCircle;

function startTimer() {
    startTime = Date.now();
    progressCircle = document.getElementById('timer-progress');
    timerInterval = setInterval(updateTimer, 100);
    document.getElementById('scraping-timer').style.color = '#4CAF50'; // Green
}

function stopTimer() {
    clearInterval(timerInterval);
    document.getElementById('scraping-timer').style.color = '#F44336'; // Red
}

function updateTimer() {
    const elapsed = Date.now() - startTime;
    const seconds = Math.floor(elapsed / 1000);
    
    // Update text timer
    document.getElementById('scraping-timer').textContent = formatTime(elapsed);
    
    // Update circle progress (for 60 second max)
    if (progressCircle) {
        const progress = (seconds % 60) / 60 * 125.6;
        progressCircle.style.strokeDashoffset = 125.6 - progress;
    }
}

function formatTime(milliseconds) {
    const totalSeconds = Math.floor(milliseconds / 1000);
    const hours = Math.floor(totalSeconds / 3600);
    const minutes = Math.floor((totalSeconds % 3600) / 60);
    const seconds = totalSeconds % 60;
    
    return [
        hours.toString().padStart(2, '0'),
        minutes.toString().padStart(2, '0'),
        seconds.toString().padStart(2, '0')
    ].join(':');
}

// Main scraping function
async function startScraping() {
    // Collect the checked URLs from the checkboxes
    const checkedCheckboxes = document.querySelectorAll('input[type="checkbox"]:checked[data-url]');
    const urls = Array.from(checkedCheckboxes).map(checkbox => checkbox.dataset.url);

    // Fetch other form inputs
    const fetchThreads = parseInt(document.getElementById('fetchThreads').value, 10);
    const scrapeThreads = parseInt(document.getElementById('scrapeThreads').value, 10);
    // const workers = parseInt(document.getElementById('workers').value, 10);
    // const bufferLimit = parseInt(document.getElementById('bufferLimit').value, 10);
    
    // If no URLs are selected, show an error
    if (!urls.length) {
        updateStatus('Please select at least one category', 'error');
        return;
    }
    
    document.getElementById('scrapeBtn').disabled = true;
    updateStatus('Scraping in progress...', 'info');
    startTimer();
    
    try {
        const result = await ipcRenderer.invoke('scrape', { 
            urls,
            fetchThreads,
            scrapeThreads,
            // workers,
            // bufferLimit
        });

        if (result.success) {
            // displayResults(result.scrapeProducts);
            updateStatus(`Scraping completed. Found ${result.scrapeProducts} products.`, 'success');
        } else {
            updateStatus(`Error: ${result.error}`, 'error');
        }
        if (result.msg)
            updateStatus(`Message: ${result.msg}`, 'success');

    } catch (error) {
        updateStatus(`Error: ${error.message}`, 'error');
    } finally {
        stopTimer();
        document.getElementById('scrapeBtn').disabled = false;
    }
}

ipcRenderer.on('update-scraped-count', (event, count) => {
    updateStatus(`Scraped Products: ${count}...`, 'error');
  });

// Export function
// function exportData() {
//     const data = document.getElementById('results').dataset.products;
//     if (!data) {
//         updateStatus('No data to export', 'error');
//         return;
//     }
    
//     const products = JSON.parse(data);
//     const json = JSON.stringify(products, null, 2);
//     const blob = new Blob([json], { type: 'application/json' });
//     const url = URL.createObjectURL(blob);
    
//     const a = document.createElement('a');
//     a.href = url;
//     a.download = 'amazon_products.json';
//     document.body.appendChild(a);
//     a.click();
//     document.body.removeChild(a);
//     URL.revokeObjectURL(url);
    
//     updateStatus('Data exported successfully', 'success');
// }

// Display results
// function displayResults(products) {
//     const resultsDiv = document.getElementById('results');
//     resultsDiv.innerHTML = '';
//     resultsDiv.dataset.products = JSON.stringify(products);
    
//     if (products.length === 0) {
//         resultsDiv.innerHTML = '<p>No products found.</p>';
//         return;
//     }
    
//     products.forEach(product => {
//         const productDiv = document.createElement('div');
//         productDiv.className = 'product';
        
//         productDiv.innerHTML = `
//             <h3>${product.title}</h3>
//             <img src="${product.image}" alt="${product.title}" />
//             <p>ASIN: ${product.asin}</p>
//             <p>Price: ${product.price || 'N/A'}</p>
//             <p>Original Price: ${product.oldPrice || 'N/A'}</p>
//             <p>Code: ${product.code || 'N/A'}</p>
//             <p>Discount: ${product.discount || 'N/A'}</p>
//             <p><a href="${product.url}" target="_blank">View Product</a></p>
//         `;
        
//         resultsDiv.appendChild(productDiv);
//     });
// }

// Update status
function updateStatus(message, type) {
    const statusDiv = document.getElementById('status');
    statusDiv.textContent = message;
    statusDiv.style.color = type === 'error' ? 'red' : type === 'success' ? 'green' : '#666';
}

// Event listeners
document.addEventListener('DOMContentLoaded', () => {
    document.getElementById('scrapeBtn').addEventListener('click', startScraping);
    document.getElementById('exportBtn').addEventListener('click', exportData);
    
    // Clear console and show fresh logs
    console.log('%c--- FRESH LOGS START ---', 'color: green; font-size: 14px;');
    console.clear();
});