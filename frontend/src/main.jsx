import { useMemo, useState } from 'react'
import { createRoot } from 'react-dom/client'
import './styles.css'

const API_BASE = (import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000').replace(/\/$/, '')
const concernsOptions = ['암', '뇌혈관', '심혈관', '질병', '입원', '수술', '상해', '사망', '간병']
const familyOptions = ['선택', '1인 가구', '부부', '자녀 있음', '부모 부양', '기타']
const budgetOptions = ['선택', '3만원 이하', '3만~5만원', '5만~8만원', '8만~12만원', '12만원 이상']
const existingOptions = ['선택', '있음', '없음', '잘 모르겠음']

async function api(path, options = {}) {
  const response = await fetch(`${API_BASE}${path}`, {
    headers: { 'Content-Type': 'application/json', ...(options.headers || {}) },
    ...options,
  })
  const body = await response.json().catch(() => ({}))
  if (!response.ok) throw new Error(body.detail || '요청을 처리하지 못했습니다. 잠시 후 다시 시도해 주세요.')
  return body
}

function formatNumber(value) { return new Intl.NumberFormat('ko-KR').format(Number(value || 0)) }

function SectionHeading({ kicker, title, description, action }) {
  return <div className="section-heading"><div>{kicker && <p className="section-kicker">{kicker}</p>}<h2>{title}</h2>{description && <p className="section-description">{description}</p>}</div>{action}</div>
}

function LoadingLine({ children }) { return <div className="loading-line" role="status" aria-live="polite"><span className="loading-dot" />{children}</div> }

function inlineMarkdown(value, keyPrefix = 'inline') {
  const parts = String(value || '').split(/(`[^`]+`|\*\*[^*]+\*\*|__[^_]+__)/g)
  return parts.map((part, index) => {
    if (!part) return null
    if (part.startsWith('**') && part.endsWith('**')) return <strong key={`${keyPrefix}-bold-${index}`}>{part.slice(2, -2)}</strong>
    if (part.startsWith('__') && part.endsWith('__')) return <strong key={`${keyPrefix}-bold-${index}`}>{part.slice(2, -2)}</strong>
    if (part.startsWith('`') && part.endsWith('`')) return <code key={`${keyPrefix}-code-${index}`}>{part.slice(1, -1)}</code>
    return <span key={`${keyPrefix}-text-${index}`}>{part}</span>
  })
}

function MarkdownAnswer({ text }) {
  const lines = String(text || '').replace(/\r\n?/g, '\n').split('\n')
  return <div className="answer-text">{lines.map((line, index) => {
    const trimmed = line.trim()
    if (!trimmed) return <div className="answer-spacer" key={`space-${index}`} aria-hidden="true" />
    if (/^---+$/.test(trimmed)) return <hr key={`rule-${index}`} />
    const heading = trimmed.match(/^#{1,6}\s+(.+)$/)
    if (heading) return <h4 key={`heading-${index}`}>{inlineMarkdown(heading[1], `heading-${index}`)}</h4>
    const bullet = line.match(/^(\s*)[*+-]\s+(.+)$/)
    if (bullet) {
      const indent = Math.min(3, Math.floor(bullet[1].length / 2))
      return <p className="answer-bullet" style={{ marginLeft: `${indent * 16}px` }} key={`bullet-${index}`}><span aria-hidden="true">•</span>{inlineMarkdown(bullet[2], `bullet-${index}`)}</p>
    }
    return <p key={`paragraph-${index}`}>{inlineMarkdown(trimmed, `paragraph-${index}`)}</p>
  })}</div>
}

function ProductCard({ product }) {
  const score = Number(product._match_score || 0)
  const reasons = product._ai_reasons?.length ? product._ai_reasons : product._match_reasons || []
  const cautions = product._ai_cautions?.length ? product._ai_cautions : [product.caution]
  return <article className="product-card">
    <div className="product-card-top"><span className="product-type">{product.type}</span><span className="recommendation-score">추천도 {score}점</span></div>
    <h3>{product.name}</h3><p className="product-target">{product.target}</p>
    <div className="product-highlight"><span>주요 보장</span><strong>{(product.coverage || []).join(', ')}</strong></div>
    <dl className="product-facts"><div><dt>특징</dt><dd>{(product.strengths || []).join(', ') || '-'}</dd></div><div><dt>갱신 여부</dt><dd>{product.renewal}</dd></div><div><dt>보험료 예시</dt><dd>{product.premium_example}</dd></div></dl>
    <div className="score-meter" aria-label={`추천도 ${score}점`}><span style={{ width: `${Math.min(100, score)}%` }} /></div>
    <p className="score-detail">핵심 조건 {product._hard_score || 0}/70 · 설문 대응 {product._survey_points || 0}/10 · 상황 해석 {product._llm_bonus || 0}/20</p>
    <div className="reason-box"><strong>이런 점에서 잘 맞아요</strong><ul>{reasons.slice(0, 3).map((reason, index) => <li key={index}>{reason}</li>)}</ul></div>
    <div className="caution-box"><strong>가입 전 확인할 내용</strong><ul>{cautions.filter(Boolean).slice(0, 2).map((item, index) => <li key={index}>{item}</li>)}</ul></div>
    <p className="source">{product.source} · 기준일 {product.source_date}</p>
  </article>
}

function SurveyInsights({ survey, onLoad, loading }) {
  if (!survey) return <div className="empty-state"><p>고객 불편이 어떤 유형으로 나타났는지 확인해 보세요.</p><button className="secondary" onClick={onLoad} disabled={loading}>{loading ? '분석 결과를 불러오는 중…' : '설문 분석 보기'}</button></div>
  const clusters = survey.clusters || []
  const maxCount = Math.max(...clusters.map((cluster) => Number(cluster.count || 0)), 1)
  return <div className="survey-content"><div className="metric-grid"><div className="metric"><span>분석 방법</span><strong>{survey.method || '저장된 분석'}</strong></div><div className="metric"><span>클러스터 수</span><strong>{survey.n_clusters || clusters.length}</strong></div><div className="metric"><span>표시 항목</span><strong>{clusters.length}</strong></div></div><div className="insight-chart" aria-label="고객 불편 유형별 응답 수">{clusters.map((cluster) => <div className="insight-bar-row" key={cluster.label}><div className="insight-bar-label"><strong>{cluster.label}</strong><span>{formatNumber(cluster.count)}건</span></div><div className="insight-track"><span style={{ width: `${Math.max(4, (Number(cluster.count || 0) / maxCount) * 100)}%` }} /></div><p>평균 심각도 {Number(cluster.avg_severity || 0).toFixed(1)}/5</p></div>)}</div><details className="details-panel"><summary>세부 라벨과 계산 기준 보기</summary><div className="detail-table-wrap"><table className="detail-table"><thead><tr><th>불편 유형</th><th>응답 수</th><th>비율</th><th>평균 심각도</th><th>주요 표현</th></tr></thead><tbody>{clusters.map((cluster) => <tr key={cluster.label}><th>{cluster.label}</th><td>{formatNumber(cluster.count)}건</td><td>{Number(cluster.ratio || 0).toFixed(1)}%</td><td>{Number(cluster.avg_severity || 0).toFixed(2)}/5</td><td>{Array.isArray(cluster.top_terms) ? cluster.top_terms.join(', ') : cluster.top_terms || '-'}</td></tr>)}</tbody></table></div><p className="formula-note">설문 우선순위는 상대 응답 빈도, 평균 심각도, 현재 고객 조건과의 관련성을 함께 반영합니다.</p></details></div>
}

function App() {
  const [form, setForm] = useState({ insurance_age: 20, family_status: '선택', concerns: [], budget: '선택', existing: '선택', additional_note: '' })
  const [result, setResult] = useState(null); const [products, setProducts] = useState([]); const [compareIds, setCompareIds] = useState([])
  const [questions, setQuestions] = useState([]); const [questionMode, setQuestionMode] = useState('대기 중'); const [selectedQuestion, setSelectedQuestion] = useState('')
  const [answer, setAnswer] = useState(null); const [feedback, setFeedback] = useState(''); const [loading, setLoading] = useState(''); const [error, setError] = useState(''); const [survey, setSurvey] = useState(null)
  const profileValid = form.concerns.length > 0 && form.family_status !== '선택' && form.budget !== '선택' && form.existing !== '선택'
  const topProducts = products.slice(0, 3); const extraProducts = products.slice(3); const selectedCompare = products.filter((product) => compareIds.includes(product.product_id)); const comparisonProducts = selectedCompare.length ? selectedCompare : topProducts
  function update(name, value) { setForm((old) => ({ ...old, [name]: value })) }
  function toggleConcern(value) { setForm((old) => ({ ...old, concerns: old.concerns.includes(value) ? old.concerns.filter((item) => item !== value) : [...old.concerns, value] })) }
  async function runAnalysis(event) { event.preventDefault(); setError(''); if (!profileValid) { setError('관심 보장, 가족 구성, 예산, 기존 보험을 선택해 주세요.'); return }; setLoading('analysis'); try { const body = await api('/api/recommendations', { method: 'POST', body: JSON.stringify({ customer: form, use_llm: true }) }); setResult(body); setProducts(body.products || []); setCompareIds((body.products || []).slice(0, 3).map((product) => product.product_id)); setQuestions([]); setAnswer(null) } catch (err) { setError(err.message) } finally { setLoading('') } }
  async function loadSurvey() { setLoading('survey'); setError(''); try { setSurvey(await api('/api/survey-analysis')) } catch (err) { setError(err.message) } finally { setLoading('') } }
  async function generateQuestions() { if (!result) return; setLoading('questions'); setError(''); try { const body = await api('/api/questions/recommend', { method: 'POST', body: JSON.stringify({ customer: form, product_ids: comparisonProducts.map((item) => item.product_id), use_llm: true }) }); setQuestions(body.questions || []); setQuestionMode(body.mode || '완료'); setSelectedQuestion(body.questions?.[0] || '') } catch (err) { setError(err.message) } finally { setLoading('') } }
  async function askQuestion() { if (!selectedQuestion.trim()) return; setLoading('answer'); setError(''); try { setAnswer(await api('/api/questions/answer', { method: 'POST', body: JSON.stringify({ question: selectedQuestion, product_ids: comparisonProducts.map((item) => item.product_id), use_llm: true }) })) } catch (err) { setError(err.message) } finally { setLoading('') } }
  async function sendFeedback() { if (!answer || !feedback.trim()) return; setLoading('feedback'); setError(''); try { const body = await api('/api/questions/feedback', { method: 'POST', body: JSON.stringify({ question: selectedQuestion, previous_answer: answer.response, feedback, product_ids: comparisonProducts.map((item) => item.product_id), use_llm: true }) }); setAnswer((old) => ({ ...old, response: body.response, mode: body.mode })); setFeedback('') } catch (err) { setError(err.message) } finally { setLoading('') } }
  const comparisonRows = useMemo(() => [['상품 유형', ...comparisonProducts.map((item) => item.type)], ['주요 보장', ...comparisonProducts.map((item) => (item.coverage || []).join(', '))], ['갱신 여부', ...comparisonProducts.map((item) => item.renewal)], ['보험료 예시', ...comparisonProducts.map((item) => item.premium_example)], ['추천도', ...comparisonProducts.map((item) => `${item._match_score || 0}점`)], ['주의사항', ...comparisonProducts.map((item) => item.caution)]], [comparisonProducts])

  return <><header className="site-header"><div className="header-inner"><a className="wordmark" href="#top"><span className="wordmark-mark" />HANWHA LIFE</a><nav className="top-nav" aria-label="주요 메뉴"><a href="#products">상품 안내</a><a href="#compare">상품 비교</a><a href="#conversation">상담 준비</a></nav><span className="header-label">보험 상품 안내</span></div></header><main className="page-shell" id="top">
    <section className="hero"><div className="hero-copy"><p className="hero-kicker">EASY GUIDE <span>AI</span></p><h1>내게 필요한 보장을<br /><em>쉽게 확인해 보세요.</em></h1><p>고객님의 상황을 바탕으로 보험상품의 보장과 조건을 한눈에 비교해 드립니다.</p></div><div className="hero-meta"><span>한화생명 상품 안내</span><span>간단한 정보 입력으로 시작</span></div></section>
    <div className="layout"><aside className="panel input-panel"><div className="panel-title"><p className="eyebrow">YOUR PROFILE</p><h2>고객 상황 입력</h2><p className="muted">몇 가지 정보를 선택하면 나에게 맞는 상품을 먼저 보여드려요.</p></div><form onSubmit={runAnalysis}>
      <label>보험나이<input type="number" min="0" max="100" value={form.insurance_age} onChange={(e) => update('insurance_age', Number(e.target.value))} /></label><label>가족 구성<select value={form.family_status} onChange={(e) => update('family_status', e.target.value)}>{familyOptions.map((option) => <option key={option}>{option}</option>)}</select></label>
      <fieldset><legend>관심 보장 <span>복수 선택</span></legend><div className="choice-grid">{concernsOptions.map((option) => <label className={`choice ${form.concerns.includes(option) ? 'checked' : ''}`} key={option}><input type="checkbox" checked={form.concerns.includes(option)} onChange={() => toggleConcern(option)} />{option}</label>)}</div></fieldset>
      <label>월 납입 예산<select value={form.budget} onChange={(e) => update('budget', e.target.value)}>{budgetOptions.map((option) => <option key={option}>{option}</option>)}</select></label><label>기존 보험 가입 여부<select value={form.existing} onChange={(e) => update('existing', e.target.value)}>{existingOptions.map((option) => <option key={option}>{option}</option>)}</select></label>
      <label>추가 상황·희망 조건 <span className="optional">선택</span><textarea value={form.additional_note} onChange={(e) => update('additional_note', e.target.value)} placeholder="예: 가족력 때문에 암 보장을 꼼꼼히 확인하고 싶어요." /></label><button className="primary" disabled={loading === 'analysis'}>{loading === 'analysis' ? '고객 상황을 살펴보는 중…' : '내 상품 알아보기'}</button>{loading === 'analysis' && <LoadingLine>입력하신 조건을 상품 정보와 비교하고 있습니다.</LoadingLine>}
    </form></aside><div className="content-column">{error && <div className="error" role="alert"><strong>잠시 확인이 필요해요</strong><span>{error}</span></div>}
      <section className="section" id="products"><SectionHeading kicker="PROFILE & PRODUCTS" title="고객 유형 및 상품 안내" description={result ? '입력하신 조건을 기준으로 먼저 살펴볼 상품입니다.' : '고객 상황을 입력하면 나에게 맞는 상품을 확인할 수 있습니다.'} action={result && <span className="customer-pill">{result.customer_type}</span>} />{!result ? <div className="empty-state"><p>왼쪽에서 고객 상황을 입력하고 상품을 확인해 보세요.</p></div> : <><p className="result-mode">{result.recommendation_mode}</p><div className="product-grid">{topProducts.map((product) => <ProductCard key={product.product_id} product={product} />)}</div></>}</section>
      <section className="section" id="compare"><SectionHeading kicker="COMPARE" title="상품 비교" description="추천도 순으로 정렬했습니다. 다른 상품을 추가해 함께 비교할 수 있습니다." />{!result ? <div className="empty-state"><p>상품 안내를 확인한 뒤 비교할 수 있습니다.</p></div> : <><div className="compare-options">{extraProducts.map((product) => <label key={product.product_id}><input type="checkbox" checked={compareIds.includes(product.product_id)} onChange={() => setCompareIds((ids) => ids.includes(product.product_id) ? ids.filter((id) => id !== product.product_id) : [...ids, product.product_id])} />{product.name}</label>)}</div><div className="table-scroll"><table><thead><tr><th>비교 항목</th>{comparisonProducts.map((product) => <th key={product.product_id}>{product.name}<small>추천도 {product._match_score || 0}점</small></th>)}</tr></thead><tbody>{comparisonRows.map(([label, ...values]) => <tr key={label}><th>{label}</th>{values.map((value, index) => <td key={index}>{value}</td>)}</tr>)}</tbody></table></div></>}</section>
      <section className="section" id="conversation"><SectionHeading kicker="CONVERSATION" title="상담 전 질문 추천 및 AI 설명" description="궁금한 점을 정리해 상담 전에 확인해 보세요." />{!result ? <div className="empty-state"><p>상품 안내를 확인하면 상담 질문을 추천받을 수 있습니다.</p></div> : <><div className="question-toolbar"><button className="secondary" onClick={generateQuestions} disabled={loading === 'questions'}>{loading === 'questions' ? '질문을 정리하는 중…' : '상담 질문 추천받기'}</button><span className="result-mode">{questionMode}</span></div>{questions.length > 0 && <div className="question-list">{questions.map((question) => <button key={question} className={selectedQuestion === question ? 'question selected' : 'question'} onClick={() => setSelectedQuestion(question)}>{question}</button>)}</div>}<div className="ask-row"><input value={selectedQuestion} onChange={(e) => setSelectedQuestion(e.target.value)} placeholder="궁금한 내용을 직접 입력하세요." /><button className="primary ask-button" onClick={askQuestion} disabled={loading === 'answer' || !selectedQuestion.trim()}>{loading === 'answer' ? '답변을 준비하는 중…' : '답변 확인하기'}</button></div>{answer && <div className="answer-box"><p className="answer-meta">{answer.intent}<span>{answer.mode}</span></p><MarkdownAnswer text={answer.response} /><div className="feedback-row"><input value={feedback} onChange={(e) => setFeedback(e.target.value)} placeholder="답변에서 더 알고 싶은 점을 적어 주세요." /><button onClick={sendFeedback} disabled={loading === 'feedback' || !feedback.trim()}>{loading === 'feedback' ? '다시 작성 중…' : '답변 다듬기'}</button></div></div>}</>}</section>
      <section className="section" id="insights"><SectionHeading kicker="CUSTOMER INSIGHT" title="설문 기반 고객 불편 분석" description="고객 의견에서 자주 나타난 불편을 서비스 개선의 기준으로 삼았습니다." /><SurveyInsights survey={survey} onLoad={loadSurvey} loading={loading === 'survey'} /></section>
    </div></div><footer><span>한화생명 Easy Guide</span><p>본 서비스는 보험상품 이해를 돕는 안내용 프로토타입입니다. 정확한 보장 내용은 공식 상품 설명서와 전문 상담을 통해 확인해 주세요.</p></footer></main></>
}

createRoot(document.getElementById('root')).render(<App />)
