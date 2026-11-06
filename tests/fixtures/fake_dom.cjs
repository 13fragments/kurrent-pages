// Minimal DOM for running the reviewer and resolver pages in plain Node.
'use strict';

class Element {
  constructor(tagName) {
    this.nodeType = 1;
    this.tagName = tagName;
    this.children = [];
    this.parentNode = null;
    this.dataset = {};
    this.style = {};
    this.className = '';
    this.id = '';
    this.name = '';
    this.value = '';
    this.checked = false;
    this.hidden = false;
    this.disabled = false;
    this.type = '';
    this.files = [];
    this.listeners = {};
    this._textContent = '';
  }
  set textContent(value) { this._textContent = String(value ?? ''); this.children = []; }
  get textContent() {
    return this._textContent + this.children.map((child) => child.textContent || '').join('');
  }
  appendChild(child) { child.parentNode = this; this.children.push(child); return child; }
  addEventListener(name, callback) { (this.listeners[name] ||= []).push(callback); }
  dispatchEvent(name, event = {}) { for (const callback of this.listeners[name] || []) callback(event); }
  click() { this.dispatchEvent('click', {target: this}); }
  remove() {
    if (!this.parentNode) return;
    this.parentNode.children = this.parentNode.children.filter((child) => child !== this);
    this.parentNode = null;
  }
  contains(node) { return node === this || this.children.some((child) => child.nodeType === 1 && child.contains(node)); }
  querySelector(selector) { return this.querySelectorAll(selector)[0] || null; }
  querySelectorAll(selector) {
    const selectors = selector.split(',').map((part) => part.trim()).filter(Boolean);
    const found = [];
    const visit = (node) => {
      for (const child of node.children || []) {
        if (child.nodeType === 1) {
          if (selectors.some((part) => matchesComplex(child, part))) found.push(child);
          visit(child);
        }
      }
    };
    visit(this);
    return found;
  }
}
class TextNode {
  constructor(text) { this.nodeType = 3; this.textContent = String(text); this.children = []; }
}
function matchesSimple(element, selector) {
  let value = selector.trim();
  const id = value.match(/#([A-Za-z0-9_.-]+)/);
  if (id && element.id !== id[1]) return false;
  for (const [, className] of value.matchAll(/\.([A-Za-z0-9_-]+)/g)) {
    if (!String(element.className).split(/\s+/).includes(className)) return false;
  }
  const tag = value.match(/^([A-Za-z][A-Za-z0-9_-]*)/);
  return !tag || element.tagName.toLowerCase() === tag[1].toLowerCase();
}
function matchesComplex(element, selector) {
  const parts = selector.split(/\s+/).filter(Boolean);
  let current = element;
  if (!matchesSimple(current, parts[parts.length - 1])) return false;
  for (let index = parts.length - 2; index >= 0; index -= 1) {
    current = current.parentNode;
    while (current && !matchesSimple(current, parts[index])) current = current.parentNode;
    if (!current) return false;
  }
  return true;
}

module.exports = {Element, TextNode, matchesSimple, matchesComplex};
