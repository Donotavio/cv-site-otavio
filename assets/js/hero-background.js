class DataFlowBackground {
  constructor(canvas) {
    this.canvas = canvas;
    this.ctx = canvas.getContext('2d');
    this.particles = [];
    this.nodes = [];
    this.binaryStreams = [];
    this.connections = [];
    this.mouse = { x: null, y: null, radius: 120 };
    this.hue = 200;
    this.colors = this.getColors();
    
    this.resize();
    this.init();
    this.animate();
    this.setupThemeListener();
    
    window.addEventListener('resize', () => this.resize());
    canvas.addEventListener('mousemove', (e) => {
      const rect = canvas.getBoundingClientRect();
      this.mouse.x = e.clientX - rect.left;
      this.mouse.y = e.clientY - rect.top;
    });
    canvas.addEventListener('mouseleave', () => {
      this.mouse.x = null;
      this.mouse.y = null;
    });
  }
  
  resize() {
    this.canvas.width = this.canvas.offsetWidth;
    this.canvas.height = this.canvas.offsetHeight;
  }
  
  getColors() {
    const style = getComputedStyle(document.documentElement);
    return {
      bg: style.getPropertyValue('--canvas-bg').trim(),
      particle: style.getPropertyValue('--canvas-particle').trim(),
      connection: style.getPropertyValue('--canvas-connection').trim(),
      nodeBlue: style.getPropertyValue('--canvas-node-blue').trim(),
      nodeCyan: style.getPropertyValue('--canvas-node-cyan').trim(),
      nodePurple: style.getPropertyValue('--canvas-node-purple').trim(),
      nodeGlowBlue: style.getPropertyValue('--canvas-node-glow-blue').trim(),
      nodeGlowCyan: style.getPropertyValue('--canvas-node-glow-cyan').trim(),
      nodeGlowPurple: style.getPropertyValue('--canvas-node-glow-purple').trim(),
      binary: style.getPropertyValue('--canvas-binary').trim()
    };
  }
  
  setupThemeListener() {
    const observer = new MutationObserver(() => {
      this.colors = this.getColors();
    });
    
    observer.observe(document.body, {
      attributes: true,
      attributeFilter: ['class']
    });
  }
  
  init() {
    this.particles = [];
    this.nodes = [];
    this.binaryStreams = [];
    this.connections = [];
    
    const particleCount = Math.floor((this.canvas.width * this.canvas.height) / 40000);
    for (let i = 0; i < particleCount; i++) {
      this.particles.push(new DataParticle(this.canvas));
    }
    
    const nodeCount = Math.floor((this.canvas.width * this.canvas.height) / 120000);
    for (let i = 0; i < nodeCount; i++) {
      this.nodes.push(new DataNode(this.canvas));
    }
    
    const streamCount = Math.max(5, Math.floor(this.canvas.width / 300));
    const spacing = this.canvas.width / (streamCount + 1);
    for (let i = 0; i < streamCount; i++) {
      this.binaryStreams.push(new BinaryStream(this.canvas, (i + 1) * spacing));
    }
  }
  
  animate() {
    this.ctx.clearRect(0, 0, this.canvas.width, this.canvas.height);
    this.ctx.fillStyle = this.colors.bg;
    this.ctx.fillRect(0, 0, this.canvas.width, this.canvas.height);
    
    this.binaryStreams.forEach(stream => stream.update(this.ctx, this.colors));
    
    this.drawConnections();
    
    this.particles.forEach(particle => {
      particle.update(this.mouse);
      particle.draw(this.ctx, this.colors);
    });
    
    this.nodes.forEach(node => {
      node.update(this.mouse);
      node.draw(this.ctx, this.colors);
    });
    
    this.drawDataFlow();
    
    this.hue += 0.1;
    if (this.hue > 240) this.hue = 200;
    
    requestAnimationFrame(() => this.animate());
  }
  
  drawConnections() {
    this.connections = [];
    
    for (let i = 0; i < this.particles.length; i++) {
      for (let j = i + 1; j < this.particles.length; j++) {
        const dx = this.particles[i].x - this.particles[j].x;
        const dy = this.particles[i].y - this.particles[j].y;
        const distance = Math.sqrt(dx * dx + dy * dy);
        
        if (distance < 150) {
          const baseOpacity = parseFloat(this.colors.connection.match(/[\d.]+\)$/)?.[0]) || 0.15;
          const opacity = (1 - distance / 150) * baseOpacity;
          const rgb = this.colors.connection.match(/\d+/g).slice(0, 3).join(', ');
          this.ctx.strokeStyle = `rgba(${rgb}, ${opacity})`;
          this.ctx.lineWidth = 1;
          this.ctx.beginPath();
          this.ctx.moveTo(this.particles[i].x, this.particles[i].y);
          this.ctx.lineTo(this.particles[j].x, this.particles[j].y);
          this.ctx.stroke();
          
          this.connections.push({ p1: this.particles[i], p2: this.particles[j], distance });
        }
      }
    }
    
    for (let i = 0; i < this.nodes.length; i++) {
      for (let j = i + 1; j < this.nodes.length; j++) {
        const dx = this.nodes[i].x - this.nodes[j].x;
        const dy = this.nodes[i].y - this.nodes[j].y;
        const distance = Math.sqrt(dx * dx + dy * dy);
        
        if (distance < 250) {
          const opacity = (1 - distance / 250) * 0.25;
          const gradient = this.ctx.createLinearGradient(
            this.nodes[i].x, this.nodes[i].y,
            this.nodes[j].x, this.nodes[j].y
          );
          gradient.addColorStop(0, `hsla(${this.hue}, 70%, 60%, ${opacity})`);
          gradient.addColorStop(1, `hsla(${this.hue + 20}, 70%, 60%, ${opacity})`);
          
          this.ctx.strokeStyle = gradient;
          this.ctx.lineWidth = 2;
          this.ctx.beginPath();
          this.ctx.moveTo(this.nodes[i].x, this.nodes[i].y);
          this.ctx.lineTo(this.nodes[j].x, this.nodes[j].y);
          this.ctx.stroke();
        }
      }
    }
  }
  
  drawDataFlow() {
    this.connections.forEach(conn => {
      if (Math.random() > 0.995) {
        const progress = Math.random();
        const x = conn.p1.x + (conn.p2.x - conn.p1.x) * progress;
        const y = conn.p1.y + (conn.p2.y - conn.p1.y) * progress;
        
        this.ctx.beginPath();
        this.ctx.arc(x, y, 2, 0, Math.PI * 2);
        this.ctx.fillStyle = 'rgba(34, 211, 238, 0.9)';
        this.ctx.fill();
        
        this.ctx.beginPath();
        this.ctx.arc(x, y, 6, 0, Math.PI * 2);
        this.ctx.fillStyle = 'rgba(34, 211, 238, 0.2)';
        this.ctx.fill();
      }
    });
  }
}

class DataParticle {
  constructor(canvas) {
    this.canvas = canvas;
    this.reset();
  }
  
  reset() {
    this.x = Math.random() * this.canvas.width;
    this.y = Math.random() * this.canvas.height;
    this.size = Math.random() * 2 + 1;
    this.baseX = this.x;
    this.baseY = this.y;
    this.density = Math.random() * 30 + 1;
    this.vx = (Math.random() - 0.5) * 0.5;
    this.vy = (Math.random() - 0.5) * 0.5;
  }
  
  update(mouse) {
    let dx = mouse.x - this.x;
    let dy = mouse.y - this.y;
    let distance = Math.sqrt(dx * dx + dy * dy);
    let forceDirectionX = dx / distance;
    let forceDirectionY = dy / distance;
    let maxDistance = mouse.radius;
    let force = (maxDistance - distance) / maxDistance;
    let directionX = forceDirectionX * force * this.density;
    let directionY = forceDirectionY * force * this.density;
    
    if (distance < mouse.radius && mouse.x !== null) {
      this.x -= directionX;
      this.y -= directionY;
    } else {
      if (this.x !== this.baseX) {
        let dx = this.x - this.baseX;
        this.x -= dx / 10;
      }
      if (this.y !== this.baseY) {
        let dy = this.y - this.baseY;
        this.y -= dy / 10;
      }
    }
    
    this.x += this.vx;
    this.y += this.vy;
    
    if (this.x < 0 || this.x > this.canvas.width) {
      this.vx *= -1;
      this.baseX = this.x;
    }
    if (this.y < 0 || this.y > this.canvas.height) {
      this.vy *= -1;
      this.baseY = this.y;
    }
  }
  
  draw(ctx, colors) {
    ctx.beginPath();
    ctx.arc(this.x, this.y, this.size, 0, Math.PI * 2);
    ctx.fillStyle = colors.particle;
    ctx.fill();
  }
}

class DataNode {
  constructor(canvas) {
    this.canvas = canvas;
    this.x = Math.random() * canvas.width;
    this.y = Math.random() * canvas.height;
    this.size = Math.random() * 4 + 3;
    this.pulse = Math.random() * Math.PI * 2;
    this.pulseSpeed = 0.02 + Math.random() * 0.02;
    this.vx = (Math.random() - 0.5) * 0.2;
    this.vy = (Math.random() - 0.5) * 0.2;
    this.type = Math.floor(Math.random() * 3);
  }
  
  update(mouse) {
    this.pulse += this.pulseSpeed;
    
    this.x += this.vx;
    this.y += this.vy;
    
    if (this.x < 0 || this.x > this.canvas.width) this.vx *= -1;
    if (this.y < 0 || this.y > this.canvas.height) this.vy *= -1;
    
    if (mouse.x !== null) {
      const dx = mouse.x - this.x;
      const dy = mouse.y - this.y;
      const distance = Math.sqrt(dx * dx + dy * dy);
      
      if (distance < mouse.radius) {
        const force = (mouse.radius - distance) / mouse.radius;
        this.x -= (dx / distance) * force * 2;
        this.y -= (dy / distance) * force * 2;
      }
    }
  }
  
  draw(ctx, colors) {
    const pulseSize = this.size + Math.sin(this.pulse) * 2;
    
    ctx.beginPath();
    ctx.arc(this.x, this.y, pulseSize * 1.5, 0, Math.PI * 2);
    ctx.fillStyle = this.type === 0 
      ? colors.nodeGlowBlue
      : this.type === 1 
      ? colors.nodeGlowCyan
      : colors.nodeGlowPurple;
    ctx.fill();
    
    ctx.beginPath();
    ctx.arc(this.x, this.y, pulseSize, 0, Math.PI * 2);
    ctx.fillStyle = this.type === 0 
      ? colors.nodeBlue
      : this.type === 1 
      ? colors.nodeCyan
      : colors.nodePurple;
    ctx.fill();
    
    if (this.type === 0) {
      ctx.strokeStyle = 'rgba(255, 255, 255, 0.5)';
      ctx.lineWidth = 1;
      ctx.beginPath();
      ctx.moveTo(this.x - 3, this.y);
      ctx.lineTo(this.x + 3, this.y);
      ctx.moveTo(this.x, this.y - 3);
      ctx.lineTo(this.x, this.y + 3);
      ctx.stroke();
    }
  }
}

class BinaryStream {
  constructor(canvas, xOffset) {
    this.canvas = canvas;
    this.x = xOffset;
    this.chars = [];
    this.fontSize = 12;
    this.speed = Math.random() * 2 + 1;
    
    const charCount = Math.ceil(canvas.height / this.fontSize);
    for (let i = 0; i < charCount; i++) {
      this.chars.push({
        char: Math.random() > 0.5 ? '1' : '0',
        y: i * this.fontSize - Math.random() * canvas.height,
        opacity: Math.random() * 0.5 + 0.1
      });
    }
  }
  
  update(ctx, colors) {
    ctx.font = `${this.fontSize}px monospace`;
    
    this.chars.forEach((char, index) => {
      const rgb = colors.binary.match(/\d+/g).slice(0, 3).join(', ');
      ctx.fillStyle = `rgba(${rgb}, ${char.opacity * 0.4})`;
      ctx.fillText(char.char, this.x, char.y);
      
      char.y += this.speed;
      
      if (char.y > this.canvas.height) {
        char.y = 0;
        char.char = Math.random() > 0.5 ? '1' : '0';
        char.opacity = Math.random() * 0.5 + 0.1;
      }
      
      if (Math.random() > 0.98) {
        char.char = Math.random() > 0.5 ? '1' : '0';
      }
    });
  }
}

document.addEventListener('DOMContentLoaded', () => {
  const canvas = document.getElementById('hero-background-canvas');
  if (canvas) {
    new DataFlowBackground(canvas);
  }
});
