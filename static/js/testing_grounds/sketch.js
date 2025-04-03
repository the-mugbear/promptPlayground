let progress = 0;
let time = 0;  // Initialize time variable

function setup() {
  // Create a canvas that fills the window and attach it to the container
  let canvas = createCanvas(windowWidth, windowHeight);
  canvas.parent('sketch-container');
  background(0);
  strokeWeight(2);
}

function draw() {
  background(0, 50);
  stroke(0, 255, 255);
  noFill();
  
  // Increase progress gradually
  progress = min(progress + 0.1, 100);

  // Modify the waveform based on progress
  beginShape();
  for (let x = 0; x < width; x += 10) {
    // As progress increases, reduce noise amplitude
    let amplitude = map(progress, 0, 100, 100, 20);
    let y = height / 2 + amplitude * noise(x * 0.01, time);
    vertex(x, y);
  }
  endShape();
  
  // Draw a progress text indicator
  fill(255);
  noStroke();
  textSize(16);
  textAlign(CENTER, CENTER);
  text(`Loading ${int(progress)}%`, width / 2, height - 50);

  time += 0.01;
  
  // Once loading is complete, trigger a final reveal effect
  if (progress === 100) {
    // Implement a reassembly or transition effect here.
    // This could be a flicker, a glitch effect, or a final logo reveal.
  }
}
