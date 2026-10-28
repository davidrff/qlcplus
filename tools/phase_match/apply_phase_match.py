#!/usr/bin/env python3
from pathlib import Path
import sys

root = Path(sys.argv[1] if len(sys.argv) > 1 else '.').resolve()
efx = root/'engine/src/efx.cpp'
fix = root/'engine/src/efxfixture.cpp'
for p in (efx, fix):
    if not p.exists():
        raise SystemExit(f'Missing {p}')

def once(s, old, new, name):
    n = s.count(old)
    if n != 1:
        raise SystemExit(f'{name}: expected 1 match, got {n}')
    return s.replace(old, new, 1)

s = efx.read_text(encoding='utf-8')
s = once(s,
'''    if (isRunning())
    {
        uint fadeIn = overrideFadeInSpeed() == defaultSpeed() ? fadeInSpeed() : overrideFadeInSpeed();''',
'''    // Relative Pan/Tilt EFX use EFXFixture phase-matched handover instead
    // of growing the geometry from its centre during fade-in.
    if (isRunning() && !m_isRelative)
    {
        uint fadeIn = overrideFadeInSpeed() == defaultSpeed() ? fadeInSpeed() : overrideFadeInSpeed();''',
'efx relative fade')
efx.write_text(s, encoding='utf-8')

s = fix.read_text(encoding='utf-8')
s = once(s,
'''#include <QXmlStreamReader>
#include <QXmlStreamWriter>
#include <QDebug>
#include <math.h>
''',
'''#include <QXmlStreamReader>
#include <QXmlStreamWriter>
#include <QDateTime>
#include <QPointF>
#include <QHash>
#include <QDebug>
#include <float.h>
#include <math.h>
''',
'includes')

s = once(s,
'''#include "doc.h"

/*****************************************************************************
 * Initialization
 *****************************************************************************/
''',
'''#include "doc.h"

namespace
{
const qint64 kPMMaxAgeMs = 1500;
const int kPMSamples = 1440;

struct PMCache
{
    QPointF point;
    qint64 stamp;
    PMCache() : point(127.0, 127.0), stamp(0) {}
};

struct PMState
{
    QPointF from;
    uint elapsed;
    bool active;
    PMState() : from(127.0, 127.0), elapsed(0), active(false) {}
};

QHash<quint64, PMCache> s_pmCache;
QHash<const EFXFixture*, PMState> s_pmState;

quint64 pmKey(const GroupHead &h)
{
    return (quint64(h.fxi) << 32) | quint64(quint32(h.head));
}

float pmSmooth(float t)
{
    if (t <= 0.0f) return 0.0f;
    if (t >= 1.0f) return 1.0f;
    return t * t * (3.0f - 2.0f * t);
}
}

/*****************************************************************************
 * Initialization
 *****************************************************************************/
''',
'runtime state')

s = once(s,
'''EFXFixture::~EFXFixture()
{
}
''',
'''EFXFixture::~EFXFixture()
{
    s_pmState.remove(this);
}
''',
'destructor')

s = once(s,
'''    m_elapsed = 0;
    m_currentAngle = 0;
}

bool EFXFixture::isDone() const''',
'''    m_elapsed = 0;
    m_currentAngle = 0;
    PMState &pm = s_pmState[this];
    pm.from = QPointF(m_parent->xOffset(), m_parent->yOffset());
    pm.elapsed = 0;
    pm.active = false;
}

bool EFXFixture::isDone() const''',
'reset')

old = '''    // Fade in
    if (m_started == false)
        start(fader);

    // Scale from elapsed time in relation to overall duration to a point in a circle
    uint pos = (m_elapsed + timeOffset()) % m_parent->loopDuration();
    m_currentAngle = SCALE(float(pos),
                           float(0), float(m_parent->loopDuration()),
                           float(0), float(M_PI * 2));

    float valX = 0;
    float valY = 0;

    m_parent->calculatePoint(m_runTimeDirection, m_startOffset, m_currentAngle, &valX, &valY);

    /* Set target values on faders/universes */
'''
new = '''    const uint tick = MasterTimer::tick();
    bool justStarted = false;

    if (m_started == false)
    {
        start(fader);
        justStarted = true;
    }

    PMState &pm = s_pmState[this];
    if (justStarted && m_parent->isRelative() && m_mode == PanTilt)
    {
        QPointF from(m_parent->xOffset(), m_parent->yOffset());
        const quint64 key = pmKey(m_head);
        QHash<quint64, PMCache>::const_iterator it = s_pmCache.constFind(key);
        if (it != s_pmCache.constEnd())
        {
            const qint64 age = QDateTime::currentMSecsSinceEpoch() - it.value().stamp;
            if (age >= 0 && age <= kPMMaxAgeMs)
                from = it.value().point;
        }

        float bestAngle = 0.0f;
        float bestDist = FLT_MAX;
        const float twoPi = float(M_PI * 2.0);
        for (int i = 0; i < kPMSamples; ++i)
        {
            const float a = twoPi * float(i) / float(kPMSamples);
            float x = 0.0f, y = 0.0f;
            m_parent->calculatePoint(m_runTimeDirection, m_startOffset, a, &x, &y);
            const float dx = x - float(from.x());
            const float dy = y - float(from.y());
            const float d = dx * dx + dy * dy;
            if (d < bestDist)
            {
                bestDist = d;
                bestAngle = a;
            }
        }

        const uint loop = m_parent->loopDuration();
        if (loop > 0)
        {
            uint matched = uint((bestAngle / twoPi) * float(loop));
            if (matched >= loop) matched = loop - 1;
            const uint off = timeOffset() % loop;
            m_elapsed = (matched + loop - off) % loop;
        }
        pm.from = from;
        pm.elapsed = 0;
        pm.active = true;
    }

    // Scale from elapsed time in relation to overall duration to a point in a circle
    uint pos = (m_elapsed + timeOffset()) % m_parent->loopDuration();
    m_currentAngle = SCALE(float(pos),
                           float(0), float(m_parent->loopDuration()),
                           float(0), float(M_PI * 2));

    float valX = 0;
    float valY = 0;
    m_parent->calculatePoint(m_runTimeDirection, m_startOffset, m_currentAngle, &valX, &valY);

    if (m_parent->isRelative() && m_mode == PanTilt)
    {
        const uint fadeIn = m_parent->overrideFadeInSpeed() == Function::defaultSpeed()
                          ? m_parent->fadeInSpeed() : m_parent->overrideFadeInSpeed();
        if (pm.active && fadeIn > 0)
        {
            const float linear = float(pm.elapsed) / float(fadeIn);
            const float t = pmSmooth(linear);
            valX = float(pm.from.x()) + (valX - float(pm.from.x())) * t;
            valY = float(pm.from.y()) + (valY - float(pm.from.y())) * t;
            if (linear >= 1.0f) pm.active = false;
            else pm.elapsed += tick;
        }
        else
        {
            pm.active = false;
        }

        PMCache &cache = s_pmCache[pmKey(m_head)];
        cache.point = QPointF(valX, valY);
        cache.stamp = QDateTime::currentMSecsSinceEpoch();
    }

    /* Set target values on faders/universes */
'''
s = once(s, old, new, 'nextStep')
fix.write_text(s, encoding='utf-8')
print('QLC+ 4.14.4 Phase Match PM1 applied.')
