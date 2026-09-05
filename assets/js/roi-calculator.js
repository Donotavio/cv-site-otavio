// ROI Calculator Logic
const ROICalculator = {
  inputs: {
    teamSize: 5,
    dataVolume: 500, // GB
    cloudProvider: 'azure'
  },

  // Formulas baseadas em benchmarks reais de mercado
  calculations: {
    costSavings: {
      azure: (teamSize, dataVolume) => {
        const baselineCost = (teamSize * 15000) + (dataVolume * 0.5);
        const lakehouseCost = baselineCost * 0.7; // 30% redução
        return Math.round(baselineCost - lakehouseCost);
      },
      gcp: (teamSize, dataVolume) => {
        const baselineCost = (teamSize * 14000) + (dataVolume * 0.45);
        const lakehouseCost = baselineCost * 0.72;
        return Math.round(baselineCost - lakehouseCost);
      },
      aws: (teamSize, dataVolume) => {
        const baselineCost = (teamSize * 16000) + (dataVolume * 0.55);
        const lakehouseCost = baselineCost * 0.68;
        return Math.round(baselineCost - lakehouseCost);
      }
    },

    timeReduction: (teamSize, dataVolume) => {
      // Percentual de redução de tempo baseado em complexidade
      const complexityFactor = Math.min((teamSize + dataVolume / 100) / 20, 1);
      return Math.round(35 + (complexityFactor * 25)); // 35-60% redução
    },

    governanceScore: (teamSize, dataVolume) => {
      // Score de melhoria de governança (0-100)
      const teamFactor = Math.min(teamSize / 20, 1);
      const dataFactor = Math.min(dataVolume / 2000, 1);
      return Math.round(65 + (teamFactor * 15) + (dataFactor * 20));
    },

    productivityGain: (teamSize) => {
      // Ganho de produtividade do time (%)
      return Math.round(150 + (teamSize * 10)); // 150-350%
    }
  },

  init() {
    this.setupInputs();
    this.calculate();
  },

  setupInputs() {
    // Team Size Slider
    const teamSizeInput = document.getElementById('team-size');
    const teamSizeValue = document.getElementById('team-size-value');
    
    if (teamSizeInput) {
      teamSizeInput.addEventListener('input', (e) => {
        const value = parseInt(e.target.value);
        this.inputs.teamSize = value;
        if (teamSizeValue) {
          teamSizeValue.textContent = value;
        }
        this.updateRangeProgress(teamSizeInput);
        this.calculate();
      });
      this.updateRangeProgress(teamSizeInput);
    }

    // Data Volume Slider
    const dataVolumeInput = document.getElementById('data-volume');
    const dataVolumeValue = document.getElementById('data-volume-value');
    
    if (dataVolumeInput) {
      dataVolumeInput.addEventListener('input', (e) => {
        const value = parseInt(e.target.value);
        this.inputs.dataVolume = value;
        if (dataVolumeValue) {
          const displayValue = value >= 1000 ? `${(value / 1000).toFixed(1)} TB` : `${value} GB`;
          dataVolumeValue.textContent = displayValue;
        }
        this.updateRangeProgress(dataVolumeInput);
        this.calculate();
      });
      this.updateRangeProgress(dataVolumeInput);
    }

    // Cloud Provider Select
    const cloudInput = document.getElementById('cloud-provider');
    if (cloudInput) {
      cloudInput.addEventListener('change', (e) => {
        this.inputs.cloudProvider = e.target.value;
        this.calculate();
      });
    }

    // Reset Button
    const resetBtn = document.getElementById('calculator-reset');
    if (resetBtn) {
      resetBtn.addEventListener('click', () => this.reset());
    }
  },

  updateRangeProgress(input) {
    const value = ((input.value - input.min) / (input.max - input.min)) * 100;
    input.style.setProperty('--range-progress', `${value}%`);
  },

  calculate() {
    const results = document.querySelector('.calculator-results');
    if (!results) return;

    // Add calculating state
    results.classList.add('calculating');

    // Simulate calculation delay for better UX
    setTimeout(() => {
      const { teamSize, dataVolume, cloudProvider } = this.inputs;

      // Calculate metrics
      const costSavings = this.calculations.costSavings[cloudProvider](teamSize, dataVolume);
      const timeReduction = this.calculations.timeReduction(teamSize, dataVolume);
      const governanceScore = this.calculations.governanceScore(teamSize, dataVolume);
      const productivityGain = this.calculations.productivityGain(teamSize);

      // Update DOM
      this.updateResult('cost-savings', this.formatCurrency(costSavings));
      this.updateResult('time-reduction', `${timeReduction}%`);
      this.updateResult('governance-score', `${governanceScore}/100`);
      this.updateResult('productivity-gain', `+${productivityGain}%`);

      // Remove calculating state
      results.classList.remove('calculating');

      // Trigger animation
      this.animateResults();
    }, 300);
  },

  updateResult(id, value) {
    const element = document.getElementById(id);
    if (element) {
      element.textContent = value;
    }
  },

  formatCurrency(value) {
    return new Intl.NumberFormat('pt-BR', {
      style: 'currency',
      currency: 'USD',
      maximumFractionDigits: 0
    }).format(value);
  },

  animateResults() {
    const resultCards = document.querySelectorAll('.result-card');
    resultCards.forEach((card, index) => {
      card.style.animation = 'none';
      setTimeout(() => {
        card.style.animation = `fadeInUp 0.5s ease-out ${index * 0.1}s forwards`;
      }, 10);
    });
  },

  reset() {
    // Reset to default values
    this.inputs = {
      teamSize: 5,
      dataVolume: 500,
      cloudProvider: 'azure'
    };

    // Update UI
    const teamSizeInput = document.getElementById('team-size');
    const dataVolumeInput = document.getElementById('data-volume');
    const cloudInput = document.getElementById('cloud-provider');

    if (teamSizeInput) {
      teamSizeInput.value = 5;
      this.updateRangeProgress(teamSizeInput);
      document.getElementById('team-size-value').textContent = '5';
    }

    if (dataVolumeInput) {
      dataVolumeInput.value = 500;
      this.updateRangeProgress(dataVolumeInput);
      document.getElementById('data-volume-value').textContent = '500 GB';
    }

    if (cloudInput) {
      cloudInput.value = 'azure';
    }

    // Recalculate
    this.calculate();
  }
};

// Initialize on DOM ready
document.addEventListener('DOMContentLoaded', () => {
  ROICalculator.init();
});

// Recalculate on language change
window.addEventListener('languageChanged', () => {
  ROICalculator.calculate();
});
