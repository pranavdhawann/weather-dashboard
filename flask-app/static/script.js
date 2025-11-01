let weatherChart = null;
let currentWeatherData = [];

const weatherIcons = {
    'clear sky': '☀️',
    'few clouds': '🌤️',
    'scattered clouds': '⛅',
    'broken clouds': '☁️',
    'overcast clouds': '☁️',
    'shower rain': '🌧️',
    'rain': '🌧️',
    'light rain': '🌦️',
    'drizzle': '🌦️',
    'thunderstorm': '⛈️',
    'snow': '❄️',
    'mist': '🌫️',
    'fog': '🌫️',
    'haze': '🌫️'
};

function getWeatherIcon(condition) {
    return weatherIcons[condition.toLowerCase()] || '🌡️';
}

function getWeatherClass(condition) {
    const cond = condition.toLowerCase();
    if (cond.includes('clear')) return 'clear-sky';
    if (cond.includes('cloud')) return 'clouds';
    if (cond.includes('rain') || cond.includes('drizzle')) return 'rain';
    if (cond.includes('thunder')) return 'thunderstorm';
    if (cond.includes('snow')) return 'snow';
    if (cond.includes('mist') || cond.includes('fog') || cond.includes('haze')) return 'mist';
    return '';
}

function initThemeToggle() {
    const toggle = document.getElementById('themeToggle');
    const icon = document.getElementById('themeIcon');
    const savedTheme = localStorage.getItem('theme') || 'light';

    if (savedTheme === 'dark') {
        document.body.classList.add('dark-mode');
        icon.textContent = '☀️';
    }

    toggle.addEventListener('click', () => {
        document.body.classList.toggle('dark-mode');
        const isDark = document.body.classList.contains('dark-mode');
        icon.textContent = isDark ? '☀️' : '🌙';
        localStorage.setItem('theme', isDark ? 'dark' : 'light');

        if (weatherChart) {
            updateChartTheme();
        }
    });
}

function createAnimatedBackground() {
    const bg = document.getElementById('animatedBg');
    const particles = ['☁️', '🌤️', '⛅', '🌧️', '❄️', '💨', '⚡'];

    for (let i = 0; i < 15; i++) {
        const particle = document.createElement('div');
        particle.className = 'weather-particle';
        particle.textContent = particles[Math.floor(Math.random() * particles.length)];
        particle.style.left = Math.random() * 100 + '%';
        particle.style.top = Math.random() * 100 + '%';
        particle.style.animationDelay = Math.random() * 20 + 's';
        particle.style.animationDuration = (15 + Math.random() * 10) + 's';
        bg.appendChild(particle);
    }
}

function generateInsights(data) {
    if (!data || data.length === 0) return [];

    const temps = data.map(d => d.temperature);
    const maxTemp = Math.max(...temps);
    const minTemp = Math.min(...temps);
    const hotCity = data.find(d => d.temperature === maxTemp);
    const coldCity = data.find(d => d.temperature === minTemp);
    const avgTemp = temps.reduce((a, b) => a + b, 0) / temps.length;

    const insights = [];

    const windyCities = data.filter(d => d.wind_speed > 20);
    if (windyCities.length > 0) {
        insights.push({
            type: 'warning',
            icon: '💨',
            title: 'Windy Conditions',
            content: `${windyCities.length} ${windyCities.length === 1 ? 'city has' : 'cities have'} strong winds`,
            detail: windyCities.map(c => `${c.city}: ${c.wind_speed} mph`).join(', ')
        });
    }

    if (maxTemp > 85) {
        insights.push({
            type: 'alert',
            icon: '🔥',
            title: 'Heat Advisory',
            content: `${hotCity.city} experiencing high temperatures`,
            detail: `Currently ${Math.round(maxTemp)}°F - Stay hydrated`
        });
    }

    if (minTemp < 40) {
        insights.push({
            type: 'info',
            icon: '❄️',
            title: 'Cold Weather',
            content: `${coldCity.city} has cold conditions`,
            detail: `Currently ${Math.round(minTemp)}°F - Dress warmly`
        });
    }

    const humidCities = data.filter(d => d.humidity > 80);
    if (humidCities.length > 0) {
        insights.push({
            type: 'info',
            icon: '💧',
            title: 'High Humidity',
            content: `${humidCities.length} ${humidCities.length === 1 ? 'location' : 'locations'} with humid conditions`,
            detail: humidCities.map(c => `${c.city}: ${c.humidity}%`).join(', ')
        });
    }

    insights.push({
        type: 'info',
        icon: '🌍',
        title: 'Global Average',
        content: `Average temperature across all cities`,
        detail: `${Math.round(avgTemp)}°F with ${Math.round(maxTemp - minTemp)}° variation`
    });

    return insights;
}

function displayInsights(insights) {
    const container = document.getElementById('insightsGrid');

    if (insights.length === 0) {
        container.innerHTML = `
            <div class="insight-card info">
                <div class="insight-icon">✅</div>
                <div class="insight-title">All Clear</div>
                <div class="insight-content">No significant weather events detected</div>
            </div>
        `;
        return;
    }

    container.innerHTML = insights.map(insight => `
        <div class="insight-card ${insight.type}">
            <div class="insight-icon">${insight.icon}</div>
            <div class="insight-title">${insight.title}</div>
            <div class="insight-content">${insight.content}</div>
            <div class="insight-detail">${insight.detail}</div>
        </div>
    `).join('');
}

async function loadWeatherData() {
    try {
        const response = await fetch('/api/latest');
        const data = await response.json();

        if (data.error) {
            document.getElementById('weatherCards').innerHTML =
                `<div class="loading">⚠️ ${data.error}</div>`;
            return;
        }

        if (data.length === 0) {
            document.getElementById('weatherCards').innerHTML =
                '<div class="loading">No weather data available</div>';
            return;
        }

        currentWeatherData = data;

        const insights = generateInsights(data);
        displayInsights(insights);

        // FIXED: Use local_time from API instead of timestamp
        const cardsHTML = data.map(w => `
            <div class="weather-card ${getWeatherClass(w.condition)}">
                <div class="card-header">
                    <div class="city-info">
                        <div class="city-name">${w.city}</div>
                        <div class="local-time">${w.local_time}</div>
                    </div>
                </div>
                <div class="temperature-display">
                    <div class="temperature">${Math.round(w.temperature)}°</div>
                    <div class="feels-like">Feels like ${Math.round(w.feels_like || w.temperature)}°</div>
                    <div class="condition">${w.condition}</div>
                </div>
                <div class="weather-details">
                    <div class="detail-item">
                        <span class="detail-label">Humidity</span>
                        <span class="detail-value">${w.humidity}%</span>
                    </div>
                    <div class="detail-item">
                        <span class="detail-label">Wind</span>
                        <span class="detail-value">${w.wind_speed} mph</span>
                    </div>
                </div>
                <div class="extra-details">
                    <div class="detail-item">
                        <span class="detail-label">Pressure</span>
                        <span class="detail-value">${w.pressure || 'N/A'}</span>
                    </div>
                    <div class="detail-item">
                        <span class="detail-label">Visibility</span>
                        <span class="detail-value">${w.visibility ? (w.visibility / 1000).toFixed(1) + ' km' : 'N/A'}</span>
                    </div>
                </div>
            </div>
        `).join('');

        document.getElementById('weatherCards').innerHTML = cardsHTML;

        const select = document.getElementById('citySelect');
        const forecastSelect = document.getElementById('forecastCitySelect');
        const cityOptions = '<option value="">Select a city</option>' +
            data.map(w => `<option value="${w.city}">${w.city}</option>`).join('');
        
        select.innerHTML = cityOptions;
        forecastSelect.innerHTML = '<option value="">Choose a city</option>' +
            data.map(w => `<option value="${w.city}">${w.city}</option>`).join('');

        document.getElementById('lastUpdate').textContent = new Date().toLocaleString();

        const mapIframe = document.getElementById('weatherMap');
        mapIframe.src = mapIframe.src;

    } catch (error) {
        console.error('Error:', error);
        document.getElementById('weatherCards').innerHTML =
            '<div class="loading">⚠️ Error loading data</div>';
    }
}

// FIXED: Use Flask proxy instead of calling Lambda directly
async function loadForecast(city) {
    if (!city) {
        document.getElementById('forecastGrid').innerHTML = 
            '<div class="loading">Select a city to view forecast</div>';
        return;
    }

    try {
        document.getElementById('forecastGrid').innerHTML = 
            '<div class="loading">Loading forecast</div>';

        // USE FLASK PROXY - NO MORE CORS ISSUES
        const response = await fetch(`/api/forecast/${encodeURIComponent(city)}`);
        const data = await response.json();

        if (data.error) {
            document.getElementById('forecastGrid').innerHTML = 
                `<div class="loading">⚠️ ${data.error}</div>`;
            return;
        }

        if (!data.daily || data.daily.length === 0) {
            document.getElementById('forecastGrid').innerHTML = 
                '<div class="loading">No forecast data available</div>';
            return;
        }

        const forecastHTML = data.daily.map(day => {
            const date = new Date(day.date);
            const dayName = date.toLocaleDateString('en-US', { weekday: 'short', month: 'short', day: 'numeric' });
            
            return `
                <div class="forecast-card">
                    <div class="forecast-date">${dayName}</div>
                    <div style="font-size: 2.5em; margin: 12px 0;">${getWeatherIcon(day.condition)}</div>
                    <div class="forecast-temp">${Math.round(day.temp_avg)}°F</div>
                    <div class="forecast-temp-range">
                        ${Math.round(day.temp_min)}° / ${Math.round(day.temp_max)}°
                    </div>
                    <div class="forecast-condition">${day.condition}</div>
                    <div style="font-size: 0.85em; color: var(--text-tertiary); margin-top: 8px;">
                        💧 ${Math.round(day.humidity_avg)}% | 💨 ${Math.round(day.wind_speed_avg)} mph
                    </div>
                    ${day.pop_max > 0 ? `<div style="font-size: 0.85em; color: var(--accent-blue); margin-top: 4px;">🌧 ${Math.round(day.pop_max)}% chance</div>` : ''}
                </div>
            `;
        }).join('');

        document.getElementById('forecastGrid').innerHTML = forecastHTML;

    } catch (error) {
        console.error('Error loading forecast:', error);
        document.getElementById('forecastGrid').innerHTML = 
            '<div class="loading">⚠️ Error loading forecast</div>';
    }
}

function updateChartTheme() {
    if (!weatherChart) return;

    const isDark = document.body.classList.contains('dark-mode');
    const textColor = isDark ? '#f5f5f7' : '#000000';
    const gridColor = isDark ? 'rgba(255,255,255,0.1)' : '#e5e5e7';

    weatherChart.options.scales.y.title.color = textColor;
    weatherChart.options.scales.y.ticks.color = textColor;
    weatherChart.options.scales.y.grid.color = gridColor;
    if (weatherChart.options.scales.y1) {
        weatherChart.options.scales.y1.title.color = textColor;
        weatherChart.options.scales.y1.ticks.color = textColor;
    }
    weatherChart.options.scales.x.ticks.color = textColor;
    weatherChart.options.scales.x.grid.color = gridColor;
    weatherChart.options.plugins.legend.labels.color = textColor;
    weatherChart.update();
}

async function loadTrends(city) {
    if (!city) {
        if (weatherChart) {
            weatherChart.destroy();
            weatherChart = null;
        }
        return;
    }

    try {
        const response = await fetch(`/api/trends/${encodeURIComponent(city)}`);
        const data = await response.json();

        if (data.error) {
            console.error('Error loading trends:', data.error);
            return;
        }

        console.log(`Raw data received for ${city}:`, data.labels.length, 'points');

        if (weatherChart) {
            weatherChart.destroy();
            weatherChart = null;
        }

        const isDark = document.body.classList.contains('dark-mode');
        const textColor = isDark ? '#f5f5f7' : '#000000';
        const gridColor = isDark ? 'rgba(255,255,255,0.1)' : '#e5e5e7';
        const metric = document.getElementById('metricSelect').value;
        const dateRangeSelect = document.getElementById('dateRangeSelect');
        const dateRange = dateRangeSelect ? parseInt(dateRangeSelect.value) : 7;

        console.log(`Filtering for last ${dateRange} days`);

        const now = new Date();
        const cutoffTime = new Date(now.getTime() - (dateRange * 24 * 60 * 60 * 1000));
        
        console.log('Current time:', now.toISOString());
        console.log('Cutoff time:', cutoffTime.toISOString());

        let filteredData = [];
        
        for (let i = 0; i < data.labels.length; i++) {
            try {
                let labelDate;
                const label = data.labels[i];
                
                if (label.includes('/')) {
                    const parts = label.split(' ');
                    const datePart = parts[0];
                    const timePart = parts[1];
                    
                    const [month, day] = datePart.split('/');
                    const [hour, minute] = timePart.split(':');
                    
                    labelDate = new Date(now.getFullYear(), month - 1, day, hour, minute);
                    
                    if (labelDate > now) {
                        labelDate = new Date(now.getFullYear() - 1, month - 1, day, hour, minute);
                    }
                } else {
                    labelDate = new Date(label);
                }
                
                if (!isNaN(labelDate.getTime())) {
                    if (labelDate >= cutoffTime && labelDate <= now) {
                        filteredData.push({
                            label: label,
                            date: labelDate,
                            temperature: data.temperature[i],
                            humidity: data.humidity[i]
                        });
                    }
                }
            } catch (e) {
                console.error('Error parsing date:', data.labels[i], e);
            }
        }

        console.log(`Filtered data: ${filteredData.length} points out of ${data.labels.length}`);

        if (filteredData.length === 0) {
            console.warn('No data in range, using all available data');
            filteredData = data.labels.map((label, i) => ({
                label: label,
                temperature: data.temperature[i],
                humidity: data.humidity[i]
            }));
        }

        filteredData.sort((a, b) => {
            if (a.date && b.date) return a.date - b.date;
            return 0;
        });

        const filteredLabels = filteredData.map(d => d.label);
        const filteredTemp = filteredData.map(d => d.temperature);
        const filteredHumidity = filteredData.map(d => d.humidity);

        console.log('Chart data points:', filteredLabels.length);

        const datasets = [];

        if (metric === 'all' || metric === 'temp') {
            datasets.push({
                label: 'Temperature (°F)',
                data: filteredTemp,
                borderColor: '#0071e3',
                backgroundColor: 'rgba(0,113,227,0.1)',
                borderWidth: 3,
                tension: 0.4,
                fill: true,
                yAxisID: 'y',
                pointRadius: 2,
                pointHoverRadius: 6,
                pointBackgroundColor: '#0071e3',
                pointBorderColor: '#fff',
                pointBorderWidth: 2
            });
        }

        if (metric === 'all' || metric === 'humidity') {
            datasets.push({
                label: 'Humidity (%)',
                data: filteredHumidity,
                borderColor: '#34c759',
                backgroundColor: 'rgba(52,199,89,0.1)',
                borderWidth: 3,
                tension: 0.4,
                fill: true,
                yAxisID: metric === 'humidity' ? 'y' : 'y1',
                pointRadius: 2,
                pointHoverRadius: 6,
                pointBackgroundColor: '#34c759',
                pointBorderColor: '#fff',
                pointBorderWidth: 2
            });
        }

        const ctx = document.getElementById('weatherChart');
        if (!ctx) {
            console.error('Chart canvas not found');
            return;
        }

        const chartConfig = {
            type: 'line',
            data: {
                labels: filteredLabels,
                datasets: datasets
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                interaction: {
                    mode: 'index',
                    intersect: false
                },
                plugins: {
                    legend: {
                        display: true,
                        position: 'top',
                        labels: {
                            font: { size: 13, family: 'Inter' },
                            padding: 20,
                            usePointStyle: true,
                            color: textColor
                        }
                    },
                    tooltip: {
                        backgroundColor: isDark ? '#1c1c1e' : 'white',
                        titleColor: textColor,
                        bodyColor: textColor,
                        borderColor: isDark ? '#333' : '#e5e5e7',
                        borderWidth: 1,
                        titleFont: { family: 'Inter', weight: '600' },
                        bodyFont: { family: 'Inter' },
                        cornerRadius: 8,
                        padding: 12,
                        displayColors: true
                    }
                },
                scales: {
                    x: {
                        grid: { 
                            color: gridColor,
                            drawBorder: false
                        },
                        ticks: {
                            color: textColor,
                            font: { family: 'Inter', size: 10 },
                            maxRotation: 45,
                            minRotation: 0,
                            autoSkip: true,
                            maxTicksLimit: 20
                        }
                    },
                    y: {
                        type: 'linear',
                        display: true,
                        position: 'left',
                        grid: { 
                            color: gridColor,
                            drawBorder: false
                        },
                        title: {
                            display: true,
                            text: metric === 'humidity' ? 'Humidity (%)' : 'Temperature (°F)',
                            color: textColor,
                            font: { weight: '600', family: 'Inter' }
                        },
                        ticks: { 
                            color: textColor,
                            font: { family: 'Inter', size: 11 }
                        }
                    }
                }
            }
        };

        if (metric === 'all') {
            chartConfig.options.scales.y1 = {
                type: 'linear',
                display: true,
                position: 'right',
                grid: { 
                    drawOnChartArea: false 
                },
                title: {
                    display: true,
                    text: 'Humidity (%)',
                    color: textColor,
                    font: { weight: '600', family: 'Inter' }
                },
                ticks: { 
                    color: textColor,
                    font: { family: 'Inter', size: 11 }
                }
            };
        }

        weatherChart = new Chart(ctx.getContext('2d'), chartConfig);
        console.log('✅ Chart created successfully with', filteredLabels.length, 'data points');

    } catch (error) {
        console.error('❌ Error loading trends:', error);
        if (weatherChart) {
            weatherChart.destroy();
            weatherChart = null;
        }
    }
}

function initApp() {
    initThemeToggle();
    createAnimatedBackground();
    loadWeatherData();

    document.getElementById('citySelect').addEventListener('change', (e) => {
        loadTrends(e.target.value);
    });

    document.getElementById('metricSelect').addEventListener('change', () => {
        const city = document.getElementById('citySelect').value;
        if (city) loadTrends(city);
    });

    document.getElementById('dateRangeSelect').addEventListener('change', () => {
        const city = document.getElementById('citySelect').value;
        if (city) loadTrends(city);
    });

    document.getElementById('forecastCitySelect').addEventListener('change', (e) => {
        loadForecast(e.target.value);
    });

    setInterval(loadWeatherData, 10 * 60 * 1000);
}

document.addEventListener('DOMContentLoaded', initApp);
