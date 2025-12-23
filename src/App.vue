<script setup lang="ts">
import { pinyin } from 'pinyin-pro'
import { computed, onBeforeUnmount, ref } from 'vue'

const QUESTION_BANK = {
  beginner: [
    '请你介绍一下自己。',
    '你叫什么名字？来自哪个国家？',
    '你现在是学生还是上班？你做什么？',
    '你每天几点起床？',
    '你早上一般吃什么？',
    '你最喜欢的食物是什么？',
    '你喜欢喝茶还是喝咖啡？为什么？',
    '你家有几口人？',
    '你平时怎么去学校或公司？',
    '你喜欢现在住的城市吗？',
    '你周末一般做什么？',
    '你喜欢看电影吗？喜欢看什么电影？',
    '你平时几点睡觉？',
    '你会做饭吗？你会做什么菜？',
    '你喜欢运动吗？你常做什么运动？',
    '你最喜欢的季节是什么？为什么？',
    '你常常跟朋友一起做什么？',
    '你觉得学汉语难不难？',
    '你每天学习多长时间汉语？',
    '请说一件你今天做的事情。',
  ],
  intermediate: [
    '请你简单介绍一下你的学习或工作情况。',
    '你为什么学习汉语？',
    '你觉得学习汉语最难的是什么？',
    '请说一说你最难忘的一次经历。',
    '你上个周末做了什么？',
    '你平时是怎么学习汉语的？',
    '你最喜欢的一次旅行是去哪儿？为什么？',
    '你觉得住在城市好还是农村好？为什么？',
    '你平时怎么放松自己？',
    '你最喜欢的一本书或一部电影是什么？',
    '你觉得朋友重要吗？为什么？',
    '你遇到困难的时候，一般怎么解决？',
    '你觉得学外语对工作有帮助吗？',
    '如果你有一天假期，你打算怎么安排？',
    '你觉得网络对生活有什么影响？',
    '你最喜欢的一位老师是谁？为什么？',
    '你平时喜欢一个人做事还是和别人一起？',
    '请介绍一下你最喜欢的一个地方。',
    '你对现在的生活满意吗？为什么？',
    '你对未来有什么简单的计划？',
  ],
  advanced: [
    '请你谈一谈学习汉语对你生活的影响。',
    '你怎么看待现在年轻人的生活压力？',
    '你认为成功最重要的因素是什么？',
    '请你谈谈手机对人们生活的影响。',
    '你怎么看待网络学习这种方式？',
    '有人认为钱很重要，有人认为兴趣更重要，你怎么看？',
    '请你谈一谈你对时间管理的看法。',
    '你觉得现在的人比以前更快乐吗？为什么？',
    '你怎么看待人工智能的发展？',
    '请你谈谈你最佩服的一个人。',
    '你认为工作和生活应该怎么平衡？',
    '你怎么看待失败？',
    '你觉得环境保护重要吗？为什么？',
    '请你谈谈旅游对一个地方的影响。',
    '你认为学习是为了什么？',
    '你怎么看待人与人之间的信任？',
    '你觉得现代社会最大的变化是什么？',
    '请你谈谈你对未来社会的看法。',
    '你认为语言会影响人的思维吗？',
    '你怎么看待不同文化之间的差异？',
  ],
} as const

// Default to same-origin API; file:// (packaged Electron) falls back to localhost
const ASR_ENDPOINT =
  import.meta.env.VITE_ASR_ENDPOINT ||
  (typeof window !== 'undefined' && window.location.protocol === 'file:'
    ? 'http://localhost:5001/api/asr'
    : '/api/asr')
const DIAG_ENDPOINT = import.meta.env.VITE_DIAG_ENDPOINT || ASR_ENDPOINT.replace('/api/asr', '/api/diagnose')
const GRAM_ENDPOINT = import.meta.env.VITE_GRAM_ENDPOINT || ASR_ENDPOINT.replace('/api/asr', '/api/gram-check')

type AnswerState = {
  text: string
  completed: boolean
  elapsedMs: number
  startedAt: number | null
}

type GrammarResult = {
  问题: string
  问题类型: string
  问题解析: string
  优化表达?: string
}

const answers = ref<AnswerState[]>(
  [],
)

const currentIndex = ref(0)
const selectedLevel = ref<'beginner' | 'intermediate' | 'advanced' | null>(null)
const selectedQuestions = ref<string[]>([])
const recording = ref(false)
const aiError = ref('')
const asrStatus = ref('')
const loadingAsr = ref(false)
const hintMessage = ref('')
const diagLoading = ref(false)
const diagError = ref('')
const diagText = ref('')
const diagHtml = computed(() => renderMarkdown(diagText.value))
const grammarResults = ref<(GrammarResult | string | null)[]>([])
const grammarErrors = ref<string[]>([])
const grammarLoading = ref<boolean[]>([])
const showWrongBook = ref(false)
type WrongEntry = GrammarResult & { 题目: string; 时间: string }
type WrongBookMap = Record<string, WrongEntry[]>
const wrongBookMap = ref<WrongBookMap>({})

const loadWrongBook = () => {
  try {
    const raw = localStorage.getItem('hsk-wrong-book-grouped')
    wrongBookMap.value = raw ? (JSON.parse(raw) as WrongBookMap) : {}
  } catch {
    wrongBookMap.value = {}
  }
}

const saveWrongBook = () => {
  try {
    localStorage.setItem('hsk-wrong-book-grouped', JSON.stringify(wrongBookMap.value))
  } catch {
    // ignore
  }
}

loadWrongBook()
let mediaRecorder: MediaRecorder | null = null
let mediaStream: MediaStream | null = null
let audioChunks: BlobPart[] = []
let timerHandle: number | null = null

const hasRecorderSupport = computed(
  () => typeof window !== 'undefined' && 'MediaRecorder' in window && navigator.mediaDevices?.getUserMedia,
)

const questionCount = computed(() => selectedQuestions.value.length)
const activeAnswer = computed(() => answers.value[currentIndex.value])
const allDone = computed(() => questionCount.value > 0 && answers.value.every((a) => a.completed && a.text.trim()))
const questionLabel = computed(() =>
  questionCount.value ? `${Math.min(currentIndex.value + 1, questionCount.value)}/${questionCount.value}` : '未选择',
)
const canSubmitDiag = computed(() => allDone.value && !recording.value && answers.value.every((a) => a.text.trim().length > 0))
const levelLabel = computed(() => {
  if (!selectedLevel.value) return '未选择级别'
  if (selectedLevel.value === 'beginner') return 'HSKK 初级'
  if (selectedLevel.value === 'intermediate') return 'HSKK 中级'
  return 'HSKK 高级'
})

const getPinyin = (text?: string) => (text ? pinyin(text, { toneType: 'symbol', type: 'string' }) : '')

const speakText = (text?: string) => {
  if (!text || typeof window === 'undefined' || !('speechSynthesis' in window)) return
  window.speechSynthesis.cancel()
  const utterance = new SpeechSynthesisUtterance(text)
  utterance.lang = 'zh-CN'
  utterance.rate = 1
  utterance.pitch = 1
  window.speechSynthesis.speak(utterance)
}

// No timer label displayed in UI now

const startTimer = () => {
  stopTimer()
  if (!activeAnswer.value) return
  const answer = activeAnswer.value
  if (answer) {
    answer.startedAt = Date.now() - answer.elapsedMs
    timerHandle = window.setInterval(() => {
      const current = activeAnswer.value
      if (!current || current.startedAt === null) return
      current.elapsedMs = Date.now() - current.startedAt
    }, 200)
  }
}

const escapeHtml = (str: string) =>
  str
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;')

const renderMarkdown = (text: string) => {
  if (!text) return ''
  const lines = text.split(/\r?\n/)
  const html: string[] = []
  let inList = false

  const closeList = () => {
    if (inList) {
      html.push('</ul>')
      inList = false
    }
  }

  lines.forEach((raw) => {
    const line = raw.trimEnd()
    if (!line) {
      closeList()
      return
    }

    // Headings
    const headingMatch = line.match(/^(#{1,3})\s+(.*)$/)
    if (headingMatch) {
      closeList()
      const hashes = headingMatch[1] || ''
      const textPart = headingMatch[2] || ''
      const level = hashes.length
      const content = formatInline(textPart)
      html.push(`<h${level}>${content}</h${level}>`)
      return
    }

    // List item
    if (/^[-*]\s+/.test(line)) {
      if (!inList) {
        html.push('<ul>')
        inList = true
      }
      const content = formatInline(line.replace(/^[-*]\s+/, ''))
      html.push(`<li>${content}</li>`)
      return
    }

    // Paragraph
    closeList()
    html.push(`<p>${formatInline(line)}</p>`)
  })

  closeList()
  return html.join('\n')
}

const formatInline = (text: string) => {
  const escaped = escapeHtml(text)
  // bold **text**
  const bolded = escaped.replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
  // italic *text*
  const italic = bolded.replace(/\*(.+?)\*/g, '<em>$1</em>')
  // inline code `code`
  const coded = italic.replace(/`(.+?)`/g, '<code>$1</code>')
  return coded
}

const stopTimer = () => {
  if (timerHandle) {
    window.clearInterval(timerHandle)
    timerHandle = null
  }
  const answer = activeAnswer.value
  if (answer) {
    answer.startedAt = null
  }
}

const clearMedia = () => {
  mediaRecorder?.stop()
  mediaRecorder = null
  if (mediaStream) {
    mediaStream.getTracks().forEach((t) => t.stop())
    mediaStream = null
  }
}

onBeforeUnmount(() => {
  stopTimer()
  clearMedia()
  if (typeof window !== 'undefined' && 'speechSynthesis' in window) {
    window.speechSynthesis.cancel()
  }
})

const startRecording = async () => {
  aiError.value = ''
  asrStatus.value = ''
  hintMessage.value = ''
  if (!questionCount.value) {
    hintMessage.value = '请先选择级别并生成题目。'
    return
  }
  if (!hasRecorderSupport.value) {
    hintMessage.value = '当前浏览器不支持录音，请改用支持 MediaRecorder 的桌面浏览器。'
    return
  }
  try {
    if (!mediaStream) {
      mediaStream = await navigator.mediaDevices.getUserMedia({ audio: true })
    }
    audioChunks = []
    mediaRecorder = new MediaRecorder(mediaStream)
    mediaRecorder.ondataavailable = (event) => {
      if (event.data && event.data.size > 0) audioChunks.push(event.data)
    }
    mediaRecorder.onstop = async () => {
      const blob = new Blob(audioChunks, { type: 'audio/webm' })
      audioChunks = []
      await transcribeWithAliyun(blob, currentIndex.value)
    }
    mediaRecorder.start(500)
    recording.value = true
    startTimer()
    hintMessage.value = '录音中'
  } catch (error) {
    aiError.value = error instanceof Error ? error.message : '无法开始录音'
  }
}

const finishRecording = () => {
  if (!recording.value) return
  recording.value = false
  stopTimer()
  mediaRecorder?.stop()
  if (activeAnswer.value) {
    activeAnswer.value.completed = true
  }
  hintMessage.value = '音频已提交识别，请稍等…'
}

const blobToBase64 = async (blob: Blob) =>
  new Promise<string>((resolve, reject) => {
    const reader = new FileReader()
    reader.onloadend = () => {
      const result = reader.result
      if (typeof result === 'string') resolve(result.split('base64,')[1] || result)
      else reject(new Error('无法读取音频数据'))
    }
    reader.onerror = () => reject(new Error('读取音频数据失败'))
    reader.readAsDataURL(blob)
  })

const transcribeWithAliyun = async (blob: Blob, index: number) => {
  if (!answers.value[index]) return
  loadingAsr.value = true
  aiError.value = ''
  asrStatus.value = '正在识别中...'
  try {
    const audioBase64 = await blobToBase64(blob)
  const response = await fetch(ASR_ENDPOINT, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ audioBase64, format: 'webm' }),
    })
    const data = await response.json()
    if (!response.ok) {
      const detail = typeof data?.error === 'string' ? data.error : '语音识别失败'
      throw new Error(detail)
    }
    const text = data?.text || ''
    answers.value[index].text = text
    asrStatus.value = text ? '识别完成，已填入本题。' : '识别完成，但未获取到文字。'
    hintMessage.value = ''
    if (text) {
      runGrammarCheck(index)
    }
  } catch (error) {
    aiError.value = error instanceof Error ? error.message : '识别异常'
    asrStatus.value = ''
  } finally {
    loadingAsr.value = false
  }
}

const movePrev = () => {
  if (recording.value || currentIndex.value === 0) return
  stopTimer()
  hintMessage.value = ''
  asrStatus.value = ''
  aiError.value = ''
  currentIndex.value -= 1
}

const moveNext = () => {
  if (recording.value || currentIndex.value >= questionCount.value - 1) return
  stopTimer()
  hintMessage.value = ''
  asrStatus.value = ''
  aiError.value = ''
  currentIndex.value += 1
}

const goToQuestion = (idx: number) => {
  if (recording.value) return
  if (idx === currentIndex.value || idx < 0 || idx >= questionCount.value) return
  stopTimer()
  hintMessage.value = ''
  asrStatus.value = ''
  aiError.value = ''
  currentIndex.value = idx
}

const submitDiagnosis = async () => {
  diagLoading.value = true
  diagError.value = ''
  diagText.value = ''
  try {
    const response = await fetch(DIAG_ENDPOINT, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        answers: selectedQuestions.value.map((q, idx) => ({
          question: q || '',
          answer: answers.value[idx]?.text.trim() ?? '',
        })),
      }),
    })
    const data = await response.json()
    if (!response.ok) {
      const detail = typeof data?.error === 'string' ? data.error : '诊断失败'
      throw new Error(detail)
    }
    diagText.value = data?.text || '未获取到诊断结果'
  } catch (error) {
    diagError.value = error instanceof Error ? error.message : '诊断调用异常'
  } finally {
    diagLoading.value = false
  }
}

const shufflePick = (arr: readonly string[], count: number): string[] => {
  const copy = [...arr]
  for (let i = copy.length - 1; i > 0; i -= 1) {
    const j = Math.floor(Math.random() * (i + 1))
    ;[copy[i], copy[j]] = [copy[j]!, copy[i]!]
  }
  return copy.slice(0, count)
}

const chooseLevel = (level: 'beginner' | 'intermediate' | 'advanced') => {
  selectedLevel.value = level
  selectedQuestions.value = shufflePick(QUESTION_BANK[level], 10)
  answers.value = selectedQuestions.value.map(() => ({
    text: '',
    completed: false,
    elapsedMs: 0,
    startedAt: null,
  }))
  grammarResults.value = selectedQuestions.value.map(() => null)
  grammarErrors.value = selectedQuestions.value.map(() => '')
  grammarLoading.value = selectedQuestions.value.map(() => false)
  currentIndex.value = 0
  showWrongBook.value = false
  hintMessage.value = ''
  asrStatus.value = ''
  aiError.value = ''
}

const resetLevel = () => {
  selectedLevel.value = null
  selectedQuestions.value = []
  answers.value = []
  grammarResults.value = []
  grammarErrors.value = []
  grammarLoading.value = []
  currentIndex.value = 0
  showWrongBook.value = false
  hintMessage.value = ''
  asrStatus.value = ''
  aiError.value = ''
  diagText.value = ''
  diagError.value = ''
}
const runGrammarCheck = async (idx: number) => {
  if (!selectedQuestions.value[idx]) return
  const answer = answers.value[idx]?.text.trim()
  if (!answer) return
  grammarLoading.value[idx] = true
  grammarErrors.value[idx] = ''
  grammarResults.value[idx] = null
  try {
    const response = await fetch(GRAM_ENDPOINT, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        question: selectedQuestions.value[idx] || '',
        answer,
      }),
    })
    const data = await response.json()
    if (!response.ok) {
      const detail = typeof data?.error === 'string' ? data.error : '语法检查失败'
      throw new Error(detail)
    }
    const result = data?.result
    if (result && typeof result === 'object') {
      grammarResults.value[idx] = result as GrammarResult
      const key = selectedQuestions.value[idx] || '未命题'
      const entry: WrongEntry = {
        题目: key,
        时间: new Date().toLocaleString(),
        问题: (result as any).问题 || answer,
        问题类型: (result as any).问题类型 || '',
        问题解析: (result as any).问题解析 || '',
        优化表达: (result as any).优化表达 || '',
      }
      const existing = wrongBookMap.value[key] || []
      wrongBookMap.value[key] = [entry, ...existing].slice(0, 50)
      saveWrongBook()
    } else {
      grammarResults.value[idx] = typeof result === 'string' ? result : data
    }
  } catch (error) {
    grammarErrors.value[idx] = error instanceof Error ? error.message : '语法检查异常'
  } finally {
    grammarLoading.value[idx] = false
  }
}
</script>

<template>
  <main class="page">
    <section class="top-bar">
      <div>
        <p class="eyebrow">HSKK 口语问答</p>
        <h1></h1>
      </div>
      <div class="status">
        <span class="chip" v-if="questionCount">第 {{ questionLabel }} 题</span>
        <span class="chip ghost">{{ levelLabel }}</span>
        <button class="ghost pill-btn" v-if="questionCount && !showWrongBook" @click="resetLevel">重新选级别</button>
        <button class="ghost pill-btn" @click="showWrongBook = !showWrongBook">{{ showWrongBook ? '返回答题' : '错题本' }}</button>
      </div>
    </section>

    <section v-if="showWrongBook" class="card wrong-book">
      <header class="card-header">
        <div>
          <p class="eyebrow">错题本</p>
          <h2>历史语法问题记录</h2>
        </div>
      </header>
      <div v-if="!Object.keys(wrongBookMap).length" class="empty">暂无记录，完成语法检测后会自动保存。</div>
      <div v-else class="wrong-group-list">
        <article v-for="(items, key) in wrongBookMap" :key="key" class="wrong-group">
          <div class="group-header">
            <p class="eyebrow">题目</p>
            <p class="pinyin-text" v-if="getPinyin(key)">{{ getPinyin(key) }}</p>
            <div class="question-line">
              <p class="question-text">{{ key }}</p>
              <button class="tts-btn" type="button" aria-label="播放题目" title="播放题目" @click="speakText(key)">🔊</button>
            </div>
            <p class="eyebrow">历史错误 {{ items.length }} 条</p>
          </div>
          <div class="wrong-list">
            <article v-for="(item, idx) in items" :key="key + idx" class="wrong-item">
              <p class="eyebrow">回答</p>
              <p class="final">{{ item.问题 }}</p>
              <p class="eyebrow">问题类型</p>
              <p class="final">{{ item.问题类型 || '未分类' }}</p>
              <p class="eyebrow">问题解析</p>
              <p class="final">{{ item.问题解析 || '暂无' }}</p>
              <p class="timestamp">记录时间：{{ item.时间 }}</p>
            </article>
          </div>
        </article>
      </div>
    </section>

    <section v-else-if="!questionCount" class="card selector">
      <p class="eyebrow">选择级别</p>
      <h2>请选择 HSKK 级别</h2>
      <div class="level-grid">
        <button class="level-card beginner" @click="chooseLevel('beginner')">
          <p class="eyebrow">HSKK 初级</p>
          <p>简单句，日常生活。</p>
        </button>
        <button class="level-card intermediate" @click="chooseLevel('intermediate')">
          <p class="eyebrow">HSKK 中级</p>
          <p>过去经历 + 简单观点。</p>
        </button>
        <button class="level-card advanced" @click="chooseLevel('advanced')">
          <p class="eyebrow">HSKK 高级</p>
          <p>观点表达 + 分析。</p>
        </button>
      </div>
    </section>

    <template v-else>
      <section class="overview">
        <div class="progress">
          <div class="progress-bar" :style="{ width: `${(answers.filter((a) => a.completed).length / questionCount) * 100}%` }" />
        </div>
        <div class="pill-row">
          <span
            v-for="(item, index) in answers"
            :key="index"
            class="pill"
            :class="{ done: item.completed, current: index === currentIndex, disabled: recording }"
            @click="goToQuestion(index)"
          >
            {{ index + 1 }}
          </span>
        </div>
      </section>

      <section class="card question-card">
        <header class="card-header">
          <div>
            <p class="eyebrow">当前题目</p>
            <p class="pinyin-text" v-if="getPinyin(selectedQuestions[currentIndex])">{{ getPinyin(selectedQuestions[currentIndex]) }}</p>
            <div class="question-line">
              <h2>{{ selectedQuestions[currentIndex] || '当前题目' }}</h2>
              <button
                class="tts-btn"
                type="button"
                aria-label="播放题目"
                title="播放题目"
                :disabled="!selectedQuestions[currentIndex]"
                @click="speakText(selectedQuestions[currentIndex])"
              >
                🔊
              </button>
            </div>
          </div>
          <div class="controls">
            <button class="primary bamboo-btn" :disabled="recording || loadingAsr" @click="startRecording">开始答题</button>
            <button class="danger bamboo-btn" :disabled="!recording" @click="finishRecording">结束答题</button>
          </div>
        </header>

        <div class="content">
          <div class="block">
            <div class="block-head">
              <p class="eyebrow">本题识别结果</p>
            </div>
            <div class="result-box" :class="{ empty: !(answers[currentIndex]?.text?.trim()) }">
              <p v-if="answers[currentIndex]?.text" class="result-text">
                {{ answers[currentIndex]?.text }}
              </p>
              <p v-else class="placeholder">结束录音后将显示识别结果</p>
            </div>
            <div class="info-row">
              <p class="hint" v-if="hintMessage">{{ hintMessage }}</p>
              <p class="hint" v-if="asrStatus">{{ asrStatus }}</p>
              <p class="error" v-if="aiError">{{ aiError }}</p>
              <p class="meta" v-if="loadingAsr">正在识别中...</p>
            </div>
            <div class="grammar" v-if="grammarLoading[currentIndex] || grammarResults[currentIndex] || grammarErrors[currentIndex]">
              <p class="eyebrow">本题语法检测</p>
              <p class="meta" v-if="grammarLoading[currentIndex]">AI 正在分析语法…</p>
              <p class="error" v-if="grammarErrors[currentIndex]">{{ grammarErrors[currentIndex] }}</p>
              <div v-if="grammarResults[currentIndex]" class="grammar-result">
                <template v-if="typeof grammarResults[currentIndex] === 'object' && grammarResults[currentIndex]">
                  <p><strong>问题：</strong>{{ (grammarResults[currentIndex] as any).问题 }}</p>
                  <p><strong>问题类型：</strong>{{ (grammarResults[currentIndex] as any).问题类型 }}</p>
                  <p><strong>问题解析：</strong>{{ (grammarResults[currentIndex] as any).问题解析 }}</p>
                  <p v-if="(grammarResults[currentIndex] as any).优化表达">
                    <strong>优化表达：</strong>{{ (grammarResults[currentIndex] as any).优化表达 }}
                  </p>
                </template>
                <template v-else>
                  <p>{{ grammarResults[currentIndex] }}</p>
                </template>
              </div>
            </div>
          </div>
        </div>

        <footer class="nav">
          <button class="ghost knot-btn" :disabled="currentIndex === 0 || recording" @click="movePrev">上一题</button>
          <button class="ghost knot-btn" :disabled="currentIndex === questionCount - 1 || recording" @click="moveNext">下一题</button>
        </footer>
      </section>

      <section class="card summary" v-if="allDone">
        <p class="eyebrow">全部完成</p>
        <h3>你可以检查每题文字，然后提交给大模型做语法诊断。</h3>
        <div class="diagnose-bar">
          <button class="primary" :disabled="!canSubmitDiag || diagLoading" @click="submitDiagnosis">
            {{ diagLoading ? '诊断中…' : '提交语法诊断' }}
          </button>
          <p class="error" v-if="diagError">{{ diagError }}</p>
        </div>
      </section>

      <section class="card diagnosis" v-if="diagText">
        <p class="eyebrow">AI 诊断</p>
        <div class="diag-text" v-html="diagHtml"></div>
      </section>
    </template>
  </main>
</template>

<style scoped>
:global(body) {
  --ink: #1f2933;
  --bamboo: #e7d7a4;
  --light-bamboo: #f4e9c9;
  --wood: #d8c3a5;
  --light-wood: #f9f5ec;
  --shadow: rgba(30, 30, 30, 0.15);
  --accent: #b08968;
  --accent-strong: #8c684b;
  font-family: 'PingFang SC', 'Microsoft YaHei', 'Noto Sans SC', system-ui, -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
  background:
    repeating-linear-gradient(90deg, rgba(0, 0, 0, 0.015) 0, rgba(0, 0, 0, 0.015) 1px, transparent 1px, transparent 20px),
    repeating-linear-gradient(0deg, rgba(0, 0, 0, 0.02) 0, rgba(0, 0, 0, 0.02) 2px, transparent 2px, transparent 24px),
    linear-gradient(135deg, #f7f1e4 0%, #efe5d5 50%, #f7f1e4 100%);
  color: var(--ink);
  margin: 0;
}

.page {
  max-width: 1080px;
  margin: 0 auto;
  padding: 32px 20px 64px;
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.top-bar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 12px;
}

.status {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
  justify-content: flex-end;
}

.chip {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 6px;
  padding: 6px 12px;
  border-radius: 12px;
  border: 1px solid rgba(0, 0, 0, 0.08);
  background: var(--bamboo);
  color: var(--ink);
  font-weight: 700;
  font-size: 14px;
  box-shadow: 0 1px 3px var(--shadow);
}

.chip.ghost {
  background: var(--light-wood);
  color: var(--ink);
}

.chip.active {
  background: var(--accent);
  color: #fdfbf5;
}

.overview {
  background: var(--light-wood);
  border-radius: 14px;
  padding: 12px 16px;
  box-shadow: 0 14px 40px var(--shadow);
  border: 1px solid rgba(0, 0, 0, 0.05);
}

.progress {
  height: 8px;
  background: rgba(0, 0, 0, 0.08);
  border-radius: 999px;
  overflow: hidden;
}

.progress-bar {
  height: 100%;
  background: linear-gradient(90deg, #c7a06b, #a3784b);
  transition: width 0.3s ease;
}

.pill-row {
  display: flex;
  gap: 6px;
  margin-top: 10px;
  flex-wrap: wrap;
}

.pill {
  width: 28px;
  height: 28px;
  border-radius: 8px;
  border: 1px solid rgba(0, 0, 0, 0.14);
  display: inline-flex;
  align-items: center;
  justify-content: center;
  font-weight: 600;
  color: var(--ink);
  cursor: pointer;
  transition: transform 0.15s ease, box-shadow 0.15s ease;
  background: var(--light-wood);
}

.pill.done {
  background: var(--bamboo);
  color: var(--ink);
  border-color: rgba(0, 0, 0, 0.18);
}

.pill.current {
  border-color: var(--accent);
  box-shadow: 0 0 0 2px rgba(176, 137, 104, 0.35);
  cursor: default;
}

.pill.disabled {
  opacity: 0.4;
  cursor: not-allowed;
}

.pill-btn {
  background: var(--bamboo);
  color: var(--ink);
  border: 1px solid rgba(0, 0, 0, 0.1);
  padding: 8px 12px;
  border-radius: 10px;
  font-weight: 700;
  cursor: pointer;
  box-shadow: inset 0 -2px 0 rgba(0, 0, 0, 0.07), 0 1px 2px var(--shadow);
}

.card {
  background: var(--light-wood);
  border-radius: 12px;
  padding: 18px;
  box-shadow: 0 16px 42px var(--shadow);
  width: 100%;
  box-sizing: border-box;
  border: 1px solid rgba(0, 0, 0, 0.06);
  background-image: repeating-linear-gradient(0deg, rgba(0, 0, 0, 0.025) 0, rgba(0, 0, 0, 0.025) 1px, transparent 1px, transparent 14px);
}

.question-card h2 {
  margin: 4px 0 0;
  font-weight: 800;
}

.question-line {
  display: flex;
  align-items: center;
  gap: 10px;
}

.question-line .question-text {
  margin: 0;
}

.tts-btn {
  width: 42px;
  height: 42px;
  border-radius: 50%;
  border: 1px solid rgba(116, 86, 56, 0.35);
  background: radial-gradient(circle at 30% 25%, #fff1da 0%, #f3d2a6 55%, #e7bb82 100%);
  color: #5a4a3a;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  box-shadow: inset 0 -3px 0 rgba(0, 0, 0, 0.12), 0 6px 14px rgba(88, 57, 27, 0.18);
  transition: transform 0.15s ease, box-shadow 0.15s ease, filter 0.15s ease;
  font-size: 18px;
}

.tts-btn:hover {
  transform: translateY(-2px);
  box-shadow: inset 0 -3px 0 rgba(0, 0, 0, 0.12), 0 10px 18px rgba(88, 57, 27, 0.25);
  filter: brightness(1.02);
}

.tts-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
  transform: none;
  box-shadow: inset 0 -2px 0 rgba(0, 0, 0, 0.08);
}

.pinyin-text {
  margin: 6px 0 0;
  color: #6b5b4b;
  font-size: 18px;
  line-height: 1.4;
  letter-spacing: 0.2px;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 16px;
}

.controls {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
}

.bamboo-btn {
  position: relative;
  border-radius: 14px;
  padding: 10px 18px;
  background: linear-gradient(90deg, #c6d6a3 0%, #d9e4b7 45%, #b6c98e 100%);
  border: 1px solid rgba(62, 91, 56, 0.35);
  color: #3c4a33;
  font-weight: 800;
  letter-spacing: 0.5px;
  box-shadow: inset 0 -3px 0 rgba(0, 0, 0, 0.18), 0 6px 14px rgba(47, 63, 36, 0.18);
}

.bamboo-btn::before,
.bamboo-btn::after {
  content: '';
  position: absolute;
  top: 6px;
  bottom: 6px;
  width: 6px;
  border-radius: 6px;
  background: rgba(64, 84, 52, 0.35);
  opacity: 0.45;
}

.bamboo-btn::before {
  left: 6px;
}

.bamboo-btn::after {
  right: 6px;
}

.bamboo-btn:disabled {
  opacity: 0.55;
  cursor: not-allowed;
  box-shadow: inset 0 -3px 0 rgba(0, 0, 0, 0.12);
}

.content {
  margin-top: 16px;
  display: grid;
  gap: 12px;
}

.hint {
  color: #8c684b;
  margin: 4px 0;
}

.error {
  color: #b45309;
  margin: 4px 0;
}

.meta {
  color: #6b5b4b;
  margin: 4px 0;
}

.nav {
  display: flex;
  justify-content: center;
  gap: 12px;
  margin-top: 12px;
}

.knot-btn {
  position: relative;
  padding: 10px 20px;
  border-radius: 999px;
  background: radial-gradient(circle at 30% 30%, #f49a8d 0%, #e45a4c 55%, #b63d31 100%);
  border: 1px solid rgba(121, 28, 24, 0.5);
  color: #fff7ed;
  font-weight: 800;
  letter-spacing: 0.4px;
  box-shadow: inset 0 -3px 0 rgba(0, 0, 0, 0.2), 0 8px 16px rgba(114, 39, 31, 0.25);
  overflow: visible;
}

.knot-btn::before,
.knot-btn::after {
  content: '';
  position: absolute;
  top: 50%;
  width: 22px;
  height: 22px;
  transform: translateY(-50%) rotate(45deg);
  background: radial-gradient(circle at 30% 30%, #f49a8d 0%, #e45a4c 60%, #a8352a 100%);
  border: 1px solid rgba(121, 28, 24, 0.5);
  box-shadow: inset 0 -2px 0 rgba(0, 0, 0, 0.15);
}

.knot-btn::before {
  left: -14px;
}

.knot-btn::after {
  right: -14px;
}

.knot-btn:hover {
  transform: translateY(-1px);
  box-shadow: inset 0 -3px 0 rgba(0, 0, 0, 0.2), 0 12px 18px rgba(114, 39, 31, 0.3);
}

.knot-btn:disabled {
  opacity: 0.55;
  cursor: not-allowed;
  transform: none;
  box-shadow: inset 0 -3px 0 rgba(0, 0, 0, 0.2);
}

.primary,
.ghost,
.danger {
  border: 1px solid rgba(0, 0, 0, 0.14);
  padding: 10px 14px;
  border-radius: 10px;
  font-weight: 700;
  cursor: pointer;
  transition: all 0.2s ease;
  font-size: 14px;
  box-shadow: inset 0 -3px 0 rgba(0, 0, 0, 0.08), 0 2px 6px var(--shadow);
}

.primary {
  background: linear-gradient(90deg, #caa76d, #a98654);
  color: #fdfbf5;
}

.primary:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

.ghost {
  background: var(--light-bamboo);
  color: var(--ink);
}

.danger {
  background: linear-gradient(90deg, #c77b63, #a75a43);
  color: #fdfbf5;
}

.primary.bamboo-btn,
.danger.bamboo-btn {
  border-radius: 14px;
  padding: 10px 18px;
  background: linear-gradient(90deg, #c6d6a3 0%, #d9e4b7 45%, #b6c98e 100%);
  border: 1px solid rgba(62, 91, 56, 0.35);
  color: #3c4a33;
  font-weight: 800;
  letter-spacing: 0.5px;
  box-shadow: inset 0 -3px 0 rgba(0, 0, 0, 0.18), 0 6px 14px rgba(47, 63, 36, 0.18);
}

.ghost.knot-btn {
  padding: 10px 20px;
  border-radius: 999px;
  background: radial-gradient(circle at 30% 30%, #f49a8d 0%, #e45a4c 55%, #b63d31 100%);
  border: 1px solid rgba(121, 28, 24, 0.5);
  color: #fff7ed;
  font-weight: 800;
  letter-spacing: 0.4px;
  box-shadow: inset 0 -3px 0 rgba(0, 0, 0, 0.2), 0 8px 16px rgba(114, 39, 31, 0.25);
}

.summary h3 {
  margin: 8px 0 0;
}

.diagnose-bar {
  margin-top: 12px;
  display: flex;
  align-items: center;
  gap: 12px;
  flex-wrap: wrap;
}

.diagnosis .diag-text {
  background: #0f172a;
  color: #e2e8f0;
  border-radius: 12px;
  padding: 14px;
  font-family: 'Inter', 'Noto Sans SC', system-ui, -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
  font-size: 15px;
  line-height: 1.7;
  margin: 8px 0 0;
}

.result-box {
  width: 100%;
  border: 1px solid #e2e8f0;
  border-radius: 16px;
  padding: 16px;
  min-height: 220px;
  box-sizing: border-box;
  background: #f8fafc;
  box-shadow: inset 0 1px 3px rgba(15, 23, 42, 0.06);
  display: flex;
  align-items: flex-start;
  justify-content: flex-start;
}

.result-box.empty {
  color: #94a3b8;
}

.result-text {
  margin: 0;
  font-size: 16px;
  line-height: 1.65;
  white-space: pre-wrap;
  color: #0f172a;
}

.grammar {
  margin-top: 12px;
  padding: 12px;
  border: 1px dashed rgba(0, 0, 0, 0.12);
  border-radius: 12px;
  background: rgba(255, 255, 255, 0.5);
}

.grammar-result p {
  margin: 4px 0;
  line-height: 1.5;
}

.diag-text h1,
.diag-text h2,
.diag-text h3 {
  color: #a47551;
  margin: 0 0 8px;
}

.diag-text p {
  margin: 0 0 10px;
}

.diag-text ul {
  margin: 6px 0 10px 18px;
  padding: 0;
  color: #f6f0e6;
}

.diag-text li {
  margin-bottom: 4px;
}

.diag-text code {
  background: rgba(255, 255, 255, 0.12);
  padding: 2px 6px;
  border-radius: 6px;
  font-family: 'SFMono-Regular', Consolas, 'Liberation Mono', Menlo, monospace;
  color: #f4d58d;
}

.wrong-book .wrong-list {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
  gap: 12px;
}

.wrong-group {
  border: 1px solid rgba(0, 0, 0, 0.08);
  border-radius: 14px;
  padding: 12px;
  background: #f1e6d4;
  display: flex;
  flex-direction: column;
  gap: 10px;
  margin-bottom: 14px;
}

.group-header .question-text {
  margin: 4px 0 0;
}

.group-header .question-line {
  margin-top: 4px;
}

.group-header .question-line .question-text {
  margin: 0;
}

.wrong-group .wrong-list {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(260px, 1fr));
  gap: 8px;
}

.wrong-item {
  border: 1px solid #e2e8f0;
  border-radius: 12px;
  padding: 12px;
  background: #f8fafc;
  word-break: break-word;
}

.wrong-item .timestamp {
  color: #94a3b8;
  font-size: 12px;
  margin: 6px 0 0;
}

.wrong-book .empty {
  color: #94a3b8;
  padding: 12px 0;
}

.selector .level-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
  gap: 12px;
  margin-top: 12px;
}

.level-card {
  border: 1px solid #e2e8f0;
  border-radius: 12px;
  padding: 14px;
  text-align: left;
  cursor: pointer;
  background: #f8fafc;
  transition: transform 0.12s ease, box-shadow 0.12s ease;
}

.level-card:hover {
  transform: translateY(-2px);
  box-shadow: 0 10px 30px rgba(15, 23, 42, 0.12);
}

.level-card.beginner {
  border-color: #22c55e;
}
.level-card.intermediate {
  border-color: #f59e0b;
}
.level-card.advanced {
  border-color: #6366f1;
}

.block-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
}

.chip.small {
  padding: 4px 10px;
  font-size: 12px;
}

.eyebrow {
  text-transform: uppercase;
  letter-spacing: 0.08em;
  font-size: 12px;
  color: #94a3b8;
  margin: 0 0 2px;
}

@media (max-width: 768px) {
  .top-bar {
    flex-direction: column;
    align-items: flex-start;
  }

  .card-header {
    flex-direction: column;
  }

  .nav {
    flex-direction: column;
    gap: 8px;
  }
}
</style>
